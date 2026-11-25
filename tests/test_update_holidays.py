"""公開候補の構築から保存までを実ファイルで確認する結合テスト。"""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts.fetch_csv import Download
from scripts import update_holidays
from scripts.version_manager import data_version


BASE_URL = "https://example.org/holidays/"
HEADER = "国民の祝日・休日月日,国民の祝日・休日名称\n"
ROWS = ("2030/1/1,テスト休日", "2030/5/1,テスト記念日", "2031/1/1,テスト休日")


def csv_bytes(rows, encoding="shift_jis"):
    return (HEADER + "\n".join(rows) + "\n").encode(encoding)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.public = self.root / "public"
        self.raw = self.root / "data/raw/syukujitsu.csv"
        self.csv = self.enterContext(patch("scripts.update_holidays.fetch_csv"))
        self.csv.return_value = csv_bytes(ROWS)
        self.enterContext(patch("scripts.published.download", side_effect=self.download_published))
        self.enterContext(redirect_stdout(StringIO()))
        self.initial = self.build(initial=True)

    def download_published(self, url, *, limit, accept):
        # 既存の公開ファイルを実際のデコーダー・比較処理に渡す。外部通信のみ置き換える。
        self.assertTrue(url.startswith(BASE_URL))
        target = self.public / url.removeprefix(BASE_URL)
        if not target.exists():
            raise HTTPError(url, 404, "Not found", {}, None)
        return Download(target.read_bytes(), 200, "application/json", None, None)

    def build(self, **kwargs):
        return update_holidays.build(self.root, base_url=BASE_URL, **kwargs)

    def snapshot(self):
        return {path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_invalid_fetch_or_csv_preserves_site_and_raw(self):
        before = self.snapshot()
        self.csv.side_effect = URLError("source unreachable")
        with self.assertRaises(URLError):
            self.build()
        self.assertEqual(self.snapshot(), before)
        self.csv.side_effect = None
        self.csv.return_value = csv_bytes([ROWS[0], ROWS[0]])
        with self.assertRaisesRegex(ValueError, "重複"):
            self.build()
        self.assertEqual(self.snapshot(), before)

    def test_missing_previous_year_is_not_bootstrap_even_with_initial(self):
        published_year = self.public / "holidays/2030.json"
        published_year.unlink()
        before = self.snapshot()
        with self.assertRaises(HTTPError) as failure:
            self.build(initial=True)
        self.assertEqual(failure.exception.code, 404)
        self.assertEqual(self.snapshot(), before)

    def test_inconsistent_staged_json_is_not_installed(self):
        before = self.snapshot()
        generate_site = update_holidays.generate_site

        def damage_staged_year(staging):
            generate_site(staging)
            path = staging / "holidays/2030.json"
            annual = json.loads(path.read_bytes())
            annual["holidays"]["01-01"] = "CSVと異なる名称"
            path.write_text(json.dumps(annual, ensure_ascii=False), encoding="utf-8")

        with patch.object(update_holidays, "generate_site", side_effect=damage_staged_year):
            with self.assertRaises(ValueError):
                self.build()
        self.assertEqual(self.snapshot(), before)

    def test_range_shrink_requires_approval_of_exact_candidate(self):
        before = self.snapshot()
        self.csv.return_value = csv_bytes(ROWS[:2])
        candidate_hash = data_version({"2030-01-01": "テスト休日", "2030-05-01": "テスト記念日"})
        with self.assertRaisesRegex(ValueError, candidate_hash):
            self.build()
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError):
            self.build(approve_removals=self.initial["dataVersion"])
        self.assertEqual(self.snapshot(), before)
        approved = self.build(approve_removals=candidate_hash)
        self.assertEqual((approved["dataVersion"], approved["maxYear"], approved["recordCount"]),
                         (candidate_hash, 2030, 2))
        self.assertFalse((self.public / "holidays/2031.json").exists())
        self.assertEqual(self.raw.read_bytes(), self.csv.return_value)
        self.assertEqual(json.loads((self.public / "manifest.json").read_bytes()), approved)

    def test_equivalent_csv_refreshes_check_time_only(self):
        # 公開済み時刻を既知の過去に置き、処理速度や sleep に依存せず比較する。
        published = dict(self.initial, updatedAt="2000-01-01T00:00:00+09:00",
                         checkedAt="2000-01-08T00:00:00+09:00")
        (self.public / "manifest.json").write_text(json.dumps(published), encoding="utf-8")
        annuals = {p: p.read_bytes() for p in (self.public / "holidays").iterdir()}
        self.csv.return_value = csv_bytes(reversed(ROWS), encoding="utf-8-sig")
        checked = self.build()
        self.assertGreater(checked["checkedAt"], published["checkedAt"])
        self.assertEqual(checked, published | {"checkedAt": checked["checkedAt"]})
        self.assertEqual({p: p.read_bytes() for p in annuals}, annuals)
        self.assertEqual(self.raw.read_bytes(), self.csv.return_value)

    def test_valid_addition_creates_only_new_year_data(self):
        old_year = (self.public / "holidays/2030.json").read_bytes()
        self.csv.return_value = csv_bytes((*ROWS, "2032/1/1,将来の休日"))
        result = self.build()
        added = json.loads((self.public / "holidays/2032.json").read_bytes())
        self.assertEqual(added["holidays"], {"01-01": "将来の休日"})
        self.assertEqual(added["dataVersion"], result["yearVersions"]["2032"])
        self.assertEqual(result["maxYear"], 2032)
        self.assertEqual((self.public / "holidays/2030.json").read_bytes(), old_year)

    def test_failed_site_swap_preserves_last_site_and_its_source(self):
        before = self.snapshot()
        self.csv.return_value = csv_bytes((*ROWS, "2032/1/1,将来の休日"))
        # 一度だけフォルダーの配置に失敗させ、その後のロールバックは通す。
        real_rename = os.rename
        failed = False

        def rename(src, dst):
            nonlocal failed
            if Path(dst) == self.public and not failed:
                failed = True
                raise PermissionError("publication directory busy")
            return real_rename(src, dst)

        with patch("os.rename", side_effect=rename), self.assertRaises(PermissionError):
            self.build()
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)

    def test_unmanaged_output_survives_next_build(self):
        note = self.public / "local-notes.txt"
        note.write_text("ローカルで追加", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.snapshot(), before)

    def test_failed_raw_save_preserves_last_site_and_its_source(self):
        before = self.snapshot()
        self.csv.return_value = csv_bytes((*ROWS, "2032/1/1,将来の休日"))
        real_replace = os.replace

        def replace(src, dst):
            if Path(dst) == self.raw:
                raise PermissionError("raw CSV is locked")
            return real_replace(src, dst)

        with patch("os.replace", side_effect=replace), self.assertRaises(PermissionError):
            self.build()
        self.assertEqual(self.snapshot(), before)

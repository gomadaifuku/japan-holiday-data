from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.check_official import check_official
from scripts.generate_json import build_documents


class OfficialComparisonTests(unittest.TestCase):
    def test_revised_official_csv_controls_sample_dates(self):
        records = {"2026-09-22": "休日", "2026-11-23": "勤労感謝の日"}
        manifest, years = build_documents(records, None, "2026-11-25T00:00:00+09:00")
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.csv"
            source.write_text("国民の祝日・休日月日,国民の祝日・休日名称\n"
                              "2026/9/22,休日\n2026/11/23,勤労感謝の日\n", encoding="cp932")
            (root / "holidays").mkdir()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            annual = root / "holidays" / "2026.json"
            annual.write_text(json.dumps(years[2026]), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                check_official(source, root)
            self.assertIn("2026-05-06: 公式CSVに収録なし", output.getvalue())
            self.assertIn("2026-09-22: 休日", output.getvalue())

            # 配信ファイルに以前の祝日だけが残っていれば、全件照合で不一致になる。
            years[2026]["holidays"]["05-06"] = "休日"
            annual.write_text(json.dumps(years[2026]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "2026-05-06"):
                check_official(source, root)

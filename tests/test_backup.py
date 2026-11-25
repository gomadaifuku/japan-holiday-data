import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.check_backup import check_backup
from scripts.generate_json import build_documents
from scripts.generate_site import generate_site


class BackupTests(unittest.TestCase):
    def test_extra_file_and_changed_source_block_recovery(self):
        with TemporaryDirectory() as tmp:
            public = Path(tmp) / "public"
            generate_site(public)
            manifest, years = build_documents({"2001-01-01": "元日"}, None, "2026-01-01T00:00:00+09:00")
            (public / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (public / "holidays").mkdir()
            (public / "holidays/2001.json").write_text(json.dumps(years[2001]), encoding="utf-8")
            raw = Path(tmp) / "source.csv"
            raw.write_text("国民の祝日・休日月日,国民の祝日・休日名称\n2001/1/1,元日\n", encoding="cp932")
            check_backup(public, raw)
            terms_file = public / "data-license.json"
            good_terms = terms_file.read_bytes()
            terms_file.unlink()
            with self.assertRaisesRegex(ValueError, "構成"):
                check_backup(public, raw)
            terms_file.write_text('{"softwareLicense":"MIT"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "利用条件"):
                check_backup(public, raw)
            terms_file.write_bytes(good_terms)
            extra = public / "source.csv"
            extra.write_bytes(raw.read_bytes())
            with self.assertRaises(ValueError):
                check_backup(public, raw)
            extra.unlink()
            raw.write_text("国民の祝日・休日月日,国民の祝日・休日名称\n2001/1/1,別名\n", encoding="cp932")
            with self.assertRaises(ValueError):
                check_backup(public, raw)

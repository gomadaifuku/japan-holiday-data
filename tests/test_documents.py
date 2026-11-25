import copy
import hashlib
import unittest

from scripts.generate_json import build_documents
from scripts.parse_csv import parse_csv
from scripts.validate_data import compare_records, validate_documents
from scripts.version_manager import data_version


RECORDS = {"2004-01-01": "例示A", "2004-02-29": "例示B", "2005-01-02": "休日"}
FIRST = "2004-01-03T06:15:00+09:00"
LATER = "2004-01-10T06:15:00+09:00"


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.annual = build_documents(RECORDS, None, FIRST)

    def test_t010_annual_documents_are_small_and_sorted(self):
        self.assertEqual(set(self.annual), {2004, 2005})
        first = self.annual[2004]
        self.assertEqual(first.keys(), {"schemaVersion", "year", "dataVersion", "holidays"})
        self.assertEqual(list(first["holidays"].items()), [("01-01", "例示A"), ("02-29", "例示B")])
        self.assertEqual(first["dataVersion"], self.manifest["yearVersions"]["2004"])

    def test_t011_manifest_covers_all_records(self):
        m = self.manifest
        self.assertEqual((m["minYear"], m["maxYear"], m["recordCount"]), (2004, 2005, 3))
        self.assertEqual(m["yearVersions"].keys(), {"2004", "2005"})
        self.assertEqual((m["updatedAt"], m["checkedAt"]), (FIRST, FIRST))
        self.assertEqual(validate_documents(m, self.annual, RECORDS), RECORDS)

    def test_t012_unchanged_records_preserve_versions_and_updated_at(self):
        new_manifest, years = build_documents(RECORDS.copy(), self.manifest, LATER)
        self.assertEqual(new_manifest, self.manifest | {"checkedAt": LATER})
        self.assertEqual(years, self.annual)

    def test_t013_name_change_updates_only_relevant_year(self):
        new = RECORDS | {"2004-02-29": "新名称"}
        manifest, years = build_documents(new, self.manifest, LATER)
        self.assertNotEqual(self.manifest["dataVersion"], manifest["dataVersion"])
        self.assertEqual(manifest["updatedAt"], LATER)
        self.assertNotEqual(self.annual[2004]["dataVersion"], years[2004]["dataVersion"])
        self.assertEqual(self.annual[2005], years[2005])
        self.assertEqual(compare_records(RECORDS, new)["changed"], {"2004-02-29": ["例示B", "新名称"]})

    def test_t014_new_year(self):
        new = RECORDS | {"2006-01-01": "例示"}
        manifest, years = build_documents(new, self.manifest, LATER)
        self.assertEqual(manifest["maxYear"], 2006)
        self.assertEqual(years[2006]["holidays"], {"01-01": "例示"})
        self.assertEqual(compare_records(RECORDS, new)["addedYears"], [2006])
        self.assertEqual(compare_records(RECORDS, new)["added"], {"2006-01-01": "例示"})

    def test_t015_missing_inner_year_is_invalid_and_range_shrink_is_reported(self):
        with self.assertRaisesRegex(ValueError, "欠落年"):
            build_documents(RECORDS | {"2007-02-01": "例示"}, self.manifest, LATER)
        shrunk = {day: name for day, name in RECORDS.items() if day.startswith("2004")}
        self.assertEqual(compare_records(RECORDS, shrunk)["removed"], {"2005-01-02": "休日"})

    def test_t017_timestamp_excluded_from_hash(self):
        manifest, _ = build_documents(RECORDS, None, LATER)
        self.assertEqual(manifest["dataVersion"], self.manifest["dataVersion"])
        self.assertEqual(manifest["yearVersions"], self.manifest["yearVersions"])
        wire = '[["2004-01-01","例示A"],["2004-02-29","例示B"],["2005-01-02","休日"]]'
        self.assertEqual(data_version(RECORDS), hashlib.sha256(wire.encode("utf-8")).hexdigest())

    def test_t018_reordered_csv_has_same_hash(self):
        head = "国民の祝日・休日月日,国民の祝日・休日名称\n"
        rows = ["2004/1/1,例示A", "2004/2/29,例示B", "2005/1/2,休日"]
        for order in (rows, list(reversed(rows))):
            records, _ = parse_csv((head + "\n".join(order)).encode())
            self.assertEqual(data_version(records), self.manifest["dataVersion"])

    def test_t019_invalid_manifest_types_and_values(self):
        cases = {
            "schemaVersion": [True, 1.0, 0], "minYear": [False, 0, 2006],
            "maxYear": [10000, 2006, "2005"], "recordCount": [False, 2, 3.0],
            "dataVersion": ["f" * 64, ""], "source": [None], "sourceUrl": ["http://example.invalid"],
            "updatedAt": ["2004-01-01", LATER], "checkedAt": ["2004-02-30T06:15:00+09:00"],
            "yearVersions": [[], {"2004": "x" * 64}, {}],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_documents(self.manifest | {key: value}, self.annual)
        with self.assertRaises(ValueError):
            validate_documents(self.manifest | {"extra": False}, self.annual)
        missing = self.manifest.copy()
        del missing["source"]
        with self.assertRaises(ValueError):
            validate_documents(missing, self.annual)

    def test_t019_invalid_annual_document(self):
        for key, value in (
            ("year", 2005), ("year", 2004.0), ("schemaVersion", True),
            ("extra", 0), ("dataVersion", "f" * 64), ("holidays", []),
            ("holidays", {}), ("holidays", {"4-1": "例示"}), ("holidays", {"11-31": "例示"}),
            ("holidays", {"01-01": ""}), ("holidays", {"01-01": "先\t末"}),
        ):
            annual = copy.deepcopy(self.annual)
            annual[2004][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_documents(self.manifest, annual)
        with self.assertRaises(ValueError):
            validate_documents(self.manifest, {2004: self.annual[2004]})
        with self.assertRaisesRegex(ValueError, "CSVと配信JSON"):
            validate_documents(self.manifest, self.annual, RECORDS | {"2004-01-01": "異なる名称"})

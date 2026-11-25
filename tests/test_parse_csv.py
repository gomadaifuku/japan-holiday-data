import codecs
import unittest

from scripts.parse_csv import parse_csv


HEADER = "国民の祝日・休日月日,国民の祝日・休日名称\r\n"
ROWS = '2004/2/29,テスト休日\r\n2004/01/02," 例示,休日 "\r\n'
EXPECTED = {"2004-01-02": "例示,休日", "2004-02-29": "テスト休日"}


class ParseCsvTests(unittest.TestCase):
    def test_t001_official_columns_and_date_normalization(self):
        records, codec = parse_csv((HEADER + ROWS).encode("shift_jis"))
        self.assertEqual(records, EXPECTED)
        self.assertEqual(list(records), sorted(EXPECTED))
        self.assertEqual(codec, "shift_jis")

    def test_t002_cp932_extension(self):
        records, codec = parse_csv((HEADER + "2004/5/1,例示①\n").encode("cp932"))
        self.assertEqual(records, {"2004-05-01": "例示①"})
        self.assertEqual(codec, "cp932")

    def test_t003_utf8(self):
        self.assertEqual(parse_csv((HEADER + ROWS).encode("utf-8")), (EXPECTED, "utf-8"))

    def test_ambiguous_cp932_and_shift_jis_names_fail_closed(self):
        source = (HEADER + "2004/5/1,休日～春\n").encode("cp932")
        self.assertNotEqual(source.decode("cp932"), source.decode("shift_jis"))
        with self.assertRaisesRegex(ValueError, "Shift_JIS と CP932"):
            parse_csv(source)

    def test_t004_utf8_bom(self):
        self.assertEqual(parse_csv(codecs.BOM_UTF8 + (HEADER + ROWS).encode()), (EXPECTED, "utf-8-sig"))

    def test_t005_empty_or_header_only(self):
        for data in (b"", HEADER.encode(), (HEADER + "\r\n").encode()):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_csv(data)

    def test_t006_header_and_structure_changes(self):
        for source in (
            "名称,日付\n2004/1/1,例示", HEADER + "2004/1/1",
            HEADER + "2004/1/1,例示,余分", HEADER + '2004/1/1,"閉じない',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_csv(source.encode())

    def test_t007_malformed_or_impossible_dates(self):
        for value in ("2025/2/29", "0000/1/1", "2024/13/1", "24/1/1", "20240401", "２０２４/１/１"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_csv((HEADER + f"{value},例示").encode())

    def test_t008_duplicate_normalized_date(self):
        with self.assertRaisesRegex(ValueError, "重複"):
            parse_csv((HEADER + "2004/1/1,例示\n2004/01/01,別名").encode())

    def test_t009_blank_name(self):
        with self.assertRaises(ValueError):
            parse_csv((HEADER + "2004/1/1,　 ").encode())

    def test_invalid_bytes_and_replacement_characters(self):
        for source in (b"\x81", codecs.BOM_UTF8 + b"\xff", (HEADER + "2004/1/1,休\ufffd日").encode()):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_csv(source)

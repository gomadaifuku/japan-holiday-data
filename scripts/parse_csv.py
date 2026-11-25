"""内閣府CSVを厳密にデコードし、公式の2列を日付と名称に変換する。"""

import codecs
import csv
import io
import re
from datetime import date

from .validate_data import validate_name, validate_records

HEADER = ["国民の祝日・休日月日", "国民の祝日・休日名称"]
SOURCE_DATE = re.compile(r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})")


def _decode(raw: bytes) -> tuple[str, str]:
    if not raw:
        raise ValueError("公式CSVが空です")
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    # 同じバイトでも「～」と「〜」などのUnicode表記が異なる場合は公開を止める。
    candidates = {}
    for encoding in ("shift_jis", "cp932"):
        try:
            candidates[encoding] = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    if not candidates:
        raise ValueError("公式CSVを対応文字コードでデコードできません")
    if len(set(candidates.values())) > 1:
        raise ValueError("Shift_JIS と CP932 の復号結果が異なるため、文字コードを確定できません")
    encoding, text = next(iter(candidates.items()))
    return text, encoding


def parse_csv(raw: bytes) -> tuple[dict[str, str], str]:
    text, encoding = _decode(raw)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records = {}
    try:
        if next(reader, None) != HEADER:
            raise ValueError("公式CSVのヘッダーが想定と異なります")
        for row in reader:
            if not row:  # 終端などの空行はレコードではない
                continue
            if len(row) != 2:
                raise ValueError(f"{reader.line_num}行目: 列数が2ではありません")
            match = SOURCE_DATE.fullmatch(row[0].strip())
            if not match:
                raise ValueError(f"{reader.line_num}行目: 日付形式が不正です")
            try:
                day = date(*map(int, match.groups())).isoformat()
                name = row[1].strip()
                validate_name(name)
            except ValueError as exc:
                raise ValueError(f"{reader.line_num}行目: {exc}") from exc
            if day in records:
                raise ValueError(f"{reader.line_num}行目: {day}が重複しています")
            records[day] = name
    except csv.Error as exc:
        raise ValueError(f"{reader.line_num}行目: CSV形式が不正です") from exc
    validate_records(records)
    return dict(sorted(records.items())), encoding

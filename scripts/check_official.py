"""手元の内閣府CSVから全件を読み直し、配信ファイルと独立に照合する。"""

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path


# 仕様で個別確認を求める日付。期待する名称は毎回、公式CSVから読み出す。
CHECK_DATES = (
    "2019-05-01",
    "2020-07-23", "2020-07-24",
    "2021-07-22", "2021-07-23",
    "2026-05-06", "2026-09-22", "2026-11-23",
    "2027-03-22",
)


def read_official(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "shift_jis", "cp932"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("公式CSVの文字コードを判定できません")

    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    if next(reader, None) != ["国民の祝日・休日月日", "国民の祝日・休日名称"]:
        raise ValueError("公式CSVの列名が一致しません")
    expected = {}
    for row in reader:
        if not row:
            continue
        source_date, name = row
        day = datetime.strptime(source_date.strip(), "%Y/%m/%d").date().isoformat()
        if day in expected:
            raise ValueError(f"公式CSVの日付が重複しています: {day}")
        expected[day] = name.strip()
    if not expected:
        raise ValueError("公式CSVに祝日がありません")
    return expected


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSONキーが重複しています: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def check_official(csv_path: Path, public: Path) -> None:
    expected = read_official(csv_path)
    years = {day[:4] for day in expected}
    manifest_path = public / "manifest.json"
    manifest = read_json(manifest_path)
    if (manifest["minYear"], manifest["maxYear"], manifest["recordCount"]) != (
        int(min(years)), int(max(years)), len(expected)
    ):
        raise ValueError("Manifestの対象年または件数が公式CSVと一致しません")

    files = sorted((public / "holidays").glob("*.json"))
    if {path.stem for path in files} != years or set(manifest["yearVersions"]) != years:
        raise ValueError("公式CSV・Manifest・年別JSONの対象年が一致しません")

    actual = {}
    for path in files:
        annual = read_json(path)
        if annual["year"] != int(path.stem) or annual["dataVersion"] != manifest["yearVersions"][path.stem]:
            raise ValueError(f"{path.name} の年またはバージョンが一致しません")
        for month_day, name in annual["holidays"].items():
            actual[f"{path.stem}-{month_day}"] = name

    for day in sorted(expected.keys() | actual.keys()):
        if day not in expected or day not in actual or actual[day] != expected[day]:
            raise ValueError(f"{day}: CSV={expected.get(day)!r}, JSON={actual.get(day)!r}")

    print(f"全{len(expected):,}件の日付・名称が一致 ({min(years)}–{max(years)}年、{len(years)}年分)")
    for day in CHECK_DATES:
        # 指定日は個別に結果を示す。公式CSVが改定された場合も全件照合の結果に従う。
        print(f"{day}: {expected.get(day, '公式CSVに収録なし')}")

    largest = max(files, key=lambda path: path.stat().st_size)
    for path, limit in ((manifest_path, 16 * 1024), (largest, 8 * 1024)):
        size = path.stat().st_size
        status = "目安内" if size <= limit else "目安超過"
        print(f"{path.name}: {size:,} bytes ({status}, 目安 {limit:,} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("data/raw/syukujitsu.csv"))
    parser.add_argument("--public", type=Path, default=Path("public"))
    args = parser.parse_args()
    try:
        check_official(args.csv, args.public)
    except (OSError, csv.Error, KeyError, TypeError, AttributeError, ValueError) as exc:
        print(f"照合失敗: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

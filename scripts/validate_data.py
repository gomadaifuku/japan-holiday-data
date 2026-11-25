"""正規化済みデータ、配信スキーマ、ファイル間の整合性を検証する。"""

import re
import unicodedata
from datetime import date, datetime

from .config import SCHEMA_VERSION, SOURCE_NAME, SOURCE_URL
from .version_manager import data_version


ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MONTH_DAY = re.compile(r"[0-9]{2}-[0-9]{2}")
HASH = re.compile(r"[0-9a-f]{64}")
JST_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?\+09:00")
MANIFEST_FIELDS = {
    "schemaVersion", "dataVersion", "minYear", "maxYear", "recordCount",
    "updatedAt", "checkedAt", "source", "sourceUrl", "yearVersions",
}
YEAR_FIELDS = {"schemaVersion", "dataVersion", "year", "holidays"}


def validate_name(name: str) -> None:
    if not isinstance(name, str) or not name or name.strip() != name:
        raise ValueError("祝日名称が空か、正規化されていません")
    # 不正な置換文字や制御文字を配信しない。正規の祝日名の表記は置換しない。
    if any(ch in "\ufffd\ufeff" or unicodedata.category(ch) in {"Cc", "Cs"} for ch in name):
        raise ValueError("祝日名称に制御文字または不正な文字が含まれています")


def validate_records(records: dict[str, str]) -> None:
    if not isinstance(records, dict) or not records:
        raise ValueError("祝日レコードがありません")
    years = set()
    for day, name in records.items():
        if not isinstance(day, str) or not ISO_DATE.fullmatch(day):
            raise ValueError(f"日付形式が不正です: {day!r}")
        years.add(date.fromisoformat(day).year)
        validate_name(name)
    missing = sorted(set(range(min(years), max(years) + 1)) - years)
    if missing:
        raise ValueError(f"収録年が連続していません。欠落年: {missing}")


def compare_records(old: dict[str, str], new: dict[str, str]) -> dict:
    """承認判断やジョブログに使う実データの差分。"""
    return {
        "added": {d: new[d] for d in sorted(new.keys() - old.keys())},
        "changed": {d: [old[d], new[d]] for d in sorted(old.keys() & new.keys()) if old[d] != new[d]},
        "removed": {d: old[d] for d in sorted(old.keys() - new.keys())},
        "addedYears": sorted({int(d[:4]) for d in new} - {int(d[:4]) for d in old}),
    }


def _check_document(doc, fields):
    if not isinstance(doc, dict) or doc.keys() != fields:
        raise ValueError(f"JSONの必須項目または構造が不正です。期待する項目: {sorted(fields)}")
    if type(doc["schemaVersion"]) is not int or doc["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("未対応のschemaVersionです")
    _check_hash(doc["dataVersion"])


def _check_hash(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("dataVersionがSHA-256の小文字16進表記ではありません")


def _check_time(value):
    if not isinstance(value, str) or not JST_TIMESTAMP.fullmatch(value):
        raise ValueError("日時は+09:00のISO 8601表記が必要です")
    return datetime.fromisoformat(value)


def validate_manifest(manifest: dict) -> None:
    """年別ファイル取得前にも、範囲・キーを検査する。"""
    _check_document(manifest, MANIFEST_FIELDS)
    for key in ("minYear", "maxYear", "recordCount"):
        if type(manifest[key]) is not int or manifest[key] < 1:
            raise ValueError(f"{key}は正の整数で指定してください")
    if not manifest["minYear"] <= manifest["maxYear"] <= 9999:
        raise ValueError("収録年範囲が不正です")
    versions = manifest["yearVersions"]
    expected_keys = {f"{y:04d}" for y in range(manifest["minYear"], manifest["maxYear"] + 1)}
    if not isinstance(versions, dict) or versions.keys() != expected_keys:
        raise ValueError("yearVersionsと収録年範囲が一致しません")
    for value in versions.values():
        _check_hash(value)
    if _check_time(manifest["updatedAt"]) > _check_time(manifest["checkedAt"]):
        raise ValueError("updatedAtがcheckedAtより後になっています")
    if manifest["source"] != SOURCE_NAME or manifest["sourceUrl"] != SOURCE_URL:
        raise ValueError("提供元の名称またはURLが想定と異なります")


def validate_documents(manifest: dict, years: dict[int, dict], expected_records=None) -> dict[str, str]:
    """配信JSONから元データを復元し、全件をCSVおよびManifestと突合する。"""
    validate_manifest(manifest)
    expected_years = set(range(manifest["minYear"], manifest["maxYear"] + 1))
    if not isinstance(years, dict) or any(type(y) is not int for y in years) or years.keys() != expected_years:
        raise ValueError("年別ファイル一覧がManifestと一致しません")

    records = {}
    for year, doc in sorted(years.items()):
        _check_document(doc, YEAR_FIELDS)
        if type(doc["year"]) is not int or doc["year"] != year:
            raise ValueError(f"{year}年ファイルのyearが一致しません")
        if not isinstance(doc["holidays"], dict) or not doc["holidays"]:
            raise ValueError(f"{year}年のholidaysが空または不正です")
        prefix = f"{year:04d}"
        annual = {}
        for md, name in doc["holidays"].items():
            if not isinstance(md, str) or not MONTH_DAY.fullmatch(md):
                raise ValueError(f"{year}年の日付キーが不正です: {md!r}")
            annual[f"{prefix}-{md}"] = name
        validate_records(annual)
        if data_version(annual) != doc["dataVersion"] or doc["dataVersion"] != manifest["yearVersions"][prefix]:
            raise ValueError(f"{year}年のデータバージョンが一致しません")
        records.update(annual)
    if len(records) != manifest["recordCount"] or data_version(records) != manifest["dataVersion"]:
        raise ValueError("全件数または全体データバージョンが一致しません")
    if expected_records is not None and records != expected_records:
        raise ValueError("CSVと配信JSONのレコードが一致しません")
    return records

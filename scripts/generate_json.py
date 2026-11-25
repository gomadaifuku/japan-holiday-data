"""検証対象となるManifestと年別の配信用ドキュメントを生成する。"""

from .config import SCHEMA_VERSION, SOURCE_NAME, SOURCE_URL
from .validate_data import validate_documents, validate_records
from .version_manager import data_version


def build_documents(records: dict[str, str], previous_manifest: dict | None, timestamp_iso: str):
    validate_records(records)
    grouped = {}
    for day, name in sorted(records.items()):
        grouped.setdefault(int(day[:4]), {})[day] = name

    years = {
        year: {
            "schemaVersion": SCHEMA_VERSION,
            "year": year,
            "dataVersion": data_version(annual),
            "holidays": {day[5:]: name for day, name in annual.items()},
        }
        for year, annual in grouped.items()
    }
    version = data_version(records)
    # ソースの取得時刻は内容の変更時刻やハッシュから独立して管理する。
    unchanged = previous_manifest is not None and previous_manifest["dataVersion"] == version
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "dataVersion": version,
        "minYear": min(years),
        "maxYear": max(years),
        "recordCount": len(records),
        "updatedAt": previous_manifest["updatedAt"] if unchanged else timestamp_iso,
        "checkedAt": timestamp_iso,
        "source": SOURCE_NAME,
        "sourceUrl": SOURCE_URL,
        "yearVersions": {f"{year:04d}": doc["dataVersion"] for year, doc in years.items()},
    }
    validate_documents(manifest, years, expected_records=records)
    return manifest, years

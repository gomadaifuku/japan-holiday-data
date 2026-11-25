"""Pages の既存データを復元し、公開後に実際の HTTPS 応答を検証する。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError

from .fetch_csv import download, require_https
from .generate_site import TEMPLATES
from .validate_data import validate_documents, validate_manifest


def strict_json(raw: bytes) -> dict:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON キーが重複しています: {key!r}")
            result[key] = value
        return result

    def reject_constant(token):
        raise ValueError(f"JSON の数値ではありません: {token}")

    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys, parse_constant=reject_constant)
    if not isinstance(obj, dict):
        raise ValueError("JSON のルートがオブジェクトではありません")
    return obj


def validate_license_info(info: dict) -> None:
    expected = strict_json((TEMPLATES / "data-license.json").read_bytes())
    if info != expected:
        raise ValueError("出典・利用条件が配信用の定義と一致しません")


def _base(base_url):
    parts = require_https(base_url)
    if parts.query or parts.fragment:
        raise ValueError("Pages の基本 URL にクエリやフラグメントは指定できません")
    return base_url.rstrip("/") + "/"


def _json_file(url):
    response = download(url, limit=1024 * 1024, accept="application/json")
    if response.content_type != "application/json":
        raise ValueError(f"{url} の Content-Type が {response.content_type} です")
    return strict_json(response.body), len(response.body)


def _snapshot(base, manifest):
    validate_manifest(manifest)
    years = range(manifest["minYear"], manifest["maxYear"] + 1)
    documents = {}
    sizes = []

    def get_year(year):
        return _json_file(f"{base}holidays/{year:04d}.json")

    # URL は検証済みの年範囲から組み立て、最大4接続で全収録年を取得する。
    with ThreadPoolExecutor(max_workers=4) as workers:
        for year, (document, size) in zip(years, workers.map(get_year, years), strict=True):
            documents[year] = document
            sizes.append(size)
    records = validate_documents(manifest, documents)
    return records, max(sizes)


def load_previous(base_url: str, initial: bool = False) -> tuple[dict | None, dict]:
    base = _base(base_url)
    try:
        manifest, _ = _json_file(base + "manifest.json")
    except HTTPError as exc:
        # 初回を許可した際も、許容するのは Manifest 自体の 404 に限定する。
        if exc.code == 404 and initial:
            print("明示的初回実行: 公開済み Manifest は HTTP 404")
            return None, {}
        raise
    records, _ = _snapshot(base, manifest)
    return manifest, records


def verify_once(base_url: str, expected_manifest: dict) -> None:
    base = _base(base_url)
    manifest, manifest_bytes = _json_file(base + "manifest.json")
    # ハッシュが同じでも checkedAt が古ければ前の配信を見ている。
    if manifest != expected_manifest:
        raise ValueError("公開された Manifest が今回生成した Manifest と一致しません")
    license_info, _ = _json_file(base + "data-license.json")
    validate_license_info(license_info)
    records, largest_year = _snapshot(base, manifest)
    page = download(base, limit=2 * 1024 * 1024, accept="text/html")
    if page.content_type != "text/html" or "Japan Holiday Data" not in page.body.decode("utf-8"):
        raise ValueError("公開トップページの種類または内容が不正です")
    for path, media_types in (("site.css", {"text/css"}), ("site.js", {"text/javascript", "application/javascript"})):
        asset = download(base + path, limit=512 * 1024, accept="*/*")
        if asset.content_type not in media_types or not asset.body.strip():
            raise ValueError(f"公開ページの {path} が空、または Content-Type が不正です")
    missing_year = manifest["minYear"] - 1
    try:
        download(f"{base}holidays/{missing_year:04d}.json", limit=1024 * 1024, accept="application/json")
    except HTTPError as exc:
        if exc.code != 404:
            raise
    else:
        raise ValueError(f"未収録年 {missing_year} の URL が HTTP 404 を返しません")
    print(f"公開検証成功: {base} HTTP 200, 収録年 {len(manifest['yearVersions'])}, "
          f"全 {len(records)} 件一致, 未収録年 HTTP 404, checkedAt={manifest['checkedAt']}")
    print(f"Manifest {manifest_bytes} bytes (目標 16384), 最大年別JSON {largest_year} bytes (目標 8192)")
    if manifest_bytes > 16 * 1024 or largest_year > 8 * 1024:
        print("注意: JSON が通信サイズの設計目標を超えています")


def verify(base_url, expected_manifest):
    validate_manifest(expected_manifest)
    waits = (0, 10, 30, 60, 120)
    for attempt, delay in enumerate(waits, start=1):
        if delay:
            time.sleep(delay)
        try:
            verify_once(base_url, expected_manifest)
            return
        except (OSError, ValueError) as exc:
            print(f"公開検証 {attempt}/{len(waits)}: {exc}", file=sys.stderr, flush=True)
            if attempt == len(waits):
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-manifest", required=True, type=Path)
    args = parser.parse_args()
    verify(args.base_url, strict_json(args.expected_manifest.read_bytes()))


if __name__ == "__main__":
    main()

"""公式CSVから、検証済みの静的配信ディレクトリを構築する。"""

import argparse
from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timedelta, timezone
import html
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .check_backup import list_site_files
from .config import SOURCE_URL
from .fetch_csv import fetch_csv
from .generate_json import build_documents
from .generate_site import generate_site
from .parse_csv import parse_csv
from .published import load_previous, strict_json
from .validate_data import compare_records, validate_documents

JST = timezone(timedelta(hours=9), "JST")


def write_json(path, document):
    path.write_bytes(json.dumps(document, ensure_ascii=False, separators=(",", ":"),
                                allow_nan=False).encode("utf-8"))


def log_diff(diff):
    for key, title in (("added", "追加"), ("changed", "名称変更"), ("removed", "削除")):
        values = diff[key]
        print(f"{title}: {len(values)} 件")
        for day, value in values.items():
            print(f"  {day} {json.dumps(value, ensure_ascii=False)}")
    print("追加年:", ", ".join(str(year) for year in diff["addedYears"]) or "なし")


def build(root: Path, *, base_url=None, initial=False, preview=False, approve_removals=None):
    if preview == bool(base_url) or (preview and (initial or approve_removals)):
        raise ValueError("--preview または --base-url のいずれかを指定してください。初回・削除承認は本番比較用です")
    raw = fetch_csv()
    records, encoding = parse_csv(raw)
    previous, old_records = (None, {}) if preview else load_previous(base_url, initial=initial)
    timestamp = datetime.now(JST).isoformat(timespec="seconds")
    if previous and datetime.fromisoformat(previous["checkedAt"]) > datetime.fromisoformat(timestamp):
        raise ValueError("前回確認時刻が今回より後です。システム時刻を確認してください")
    manifest, years = build_documents(records, previous, timestamp)
    diff = compare_records(old_records, records)
    version = manifest["dataVersion"]
    print(f"CSV {encoding}, {len(records)} 件, {min(years)}–{max(years)} 年")
    print("前回バージョン:", previous["dataVersion"] if previous else "なし")
    print("今回バージョン:", version)
    log_diff(diff)
    if approve_removals and approve_removals != version:
        raise ValueError("削除承認時の dataVersion が取得データと一致しません")
    if diff["removed"] and approve_removals != version:
        raise ValueError(f"削除を検出しました。差分を確認し、正当な場合のみ {version} を指定して手動承認してください")

    public = root / "public"
    if public.exists() or public.is_symlink():
        list_site_files(public, require_complete=False)
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    # 同一ファイルシステムにステージングして、全件検証が終わるまで public に触れない。
    with tempfile.TemporaryDirectory(prefix=".holiday-build-", dir=root) as temp:
        workspace = Path(temp)
        staged = workspace / "next"
        annuals = staged / "holidays"
        annuals.mkdir(parents=True)
        for year, doc in years.items():
            write_json(annuals / f"{year:04d}.json", doc)
        write_json(staged / "manifest.json", manifest)
        generate_site(staged)
        files = list_site_files(staged)
        # ディスク上の内容を読み直し、ファイル欠落やシリアライズ時の不整合も検出する。
        written_years = {int(p.stem): strict_json(p.read_bytes()) for p in files}
        validate_documents(strict_json((staged / "manifest.json").read_bytes()), written_years, records)
        for p in sorted(staged.rglob("*")):
            if p.is_file():
                print(f"{p.relative_to(staged).as_posix()}  {p.stat().st_size} B")

        csv_file = workspace / "syukujitsu.csv"
        csv_file.write_bytes(raw)
        # 旧版は別の場所に退避し、公開先と元CSVの両方が揃った時点で削除する。
        # 復元自体が失敗した場合にも、バックアップは一時ディレクトリの外に残る。
        backup = None
        if public.exists():
            backup = Path(tempfile.mkdtemp(prefix=".holiday-build-previous-", dir=root)) / "public"
            public.rename(backup)
        try:
            staged.rename(public)
            try:
                csv_file.replace(raw_dir / csv_file.name)
            except OSError:
                public.rename(staged)
                raise
        except OSError:
            if backup is not None:
                backup.rename(public)
                backup.parent.rmdir()
            raise
        if backup is not None:
            shutil.rmtree(backup.parent)
    state = "変更なし" if previous and previous["dataVersion"] == version else "変更あり"
    print(f"正常終了 ({'プレビュー' if preview else '公開候補'}・{state}), checkedAt={timestamp}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--base-url", help="前回公開版の HTTPS 基本 URL")
    mode.add_argument("--preview", action="store_true", help="公開先と比較せずローカル生成")
    parser.add_argument("--initial", action="store_true", help="初回に限り Manifest の404を許可")
    parser.add_argument("--approve-removals", metavar="SHA256", help="確認済み削除候補の dataVersion")
    args = parser.parse_args()
    root = Path.cwd()
    lock = root / ".holiday-update.lock"
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    captured = io.StringIO()
    with redirect_stdout(captured) if summary else nullcontext():
        try:
            print(f"実行日時: {datetime.now(JST).isoformat(timespec='seconds')}  取得元: {SOURCE_URL}")
            with lock.open("x", encoding="utf-8") as out:
                out.write(str(os.getpid()))
            try:
                build(root, **vars(args))
            finally:
                lock.unlink()
            status = 0
        except Exception as exc:
            print(f"異常終了: {type(exc).__name__}: {exc}")
            status = 1
    if summary:
        output = captured.getvalue()
        print(output, end="")
        # 外部由来の名称やヘッダーは文字列として表示する。完全な記録はジョブログに残す。
        with open(summary, "a", encoding="utf-8") as out:
            out.write("### 祝日データ生成\n\n<pre>" + html.escape(output[:90000]) + "</pre>\n")
    return status


if __name__ == "__main__":
    sys.exit(main())

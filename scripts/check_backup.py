"""Pages 用 Artifact のファイル構成と、同時保存した公式 CSV との対応を検査する。"""

from pathlib import Path
import re

from .parse_csv import parse_csv
from .published import strict_json, validate_license_info
from .validate_data import validate_documents

SITE_ENTRIES = {"index.html", "site.css", "site.js", ".nojekyll", "manifest.json", "data-license.json", "holidays"}


def list_site_files(public: Path, *, require_complete: bool = True) -> list[Path]:
    # アーカイブ処理がリンク先や一時ファイルを公開物に取り込むのを防ぐ。
    if public.is_symlink() or not public.is_dir():
        raise ValueError(f"不正な公開ディレクトリ: {public}")
    names = {p.name for p in public.iterdir()}
    if names - SITE_ENTRIES or (require_complete and names != SITE_ENTRIES):
        raise ValueError("公開ディレクトリの構成が想定と異なります")
    for path in public.iterdir():
        expected_type = path.is_dir() if path.name == "holidays" else path.is_file()
        if path.is_symlink() or not expected_type:
            raise ValueError(f"公開対象にできないパス: {path}")
    annual_dir = public / "holidays"
    files = sorted(annual_dir.iterdir()) if annual_dir.exists() else []
    for path in files:
        if (not re.fullmatch(r"[0-9]{4}\.json", path.name)
                or path.is_symlink() or not path.is_file()):
            raise ValueError(f"年別JSON以外のファイル: {path}")
    return files


def check_backup(public: Path, raw: Path) -> None:
    documents = {int(path.stem): strict_json(path.read_bytes()) for path in list_site_files(public)}

    validate_license_info(strict_json((public / "data-license.json").read_bytes()))
    records, encoding = parse_csv(raw.read_bytes())
    manifest = strict_json((public / "manifest.json").read_bytes())
    validate_documents(manifest, documents, expected_records=records)
    print(f"{len(documents)} 年・{len(records)} 件の公開データと保存 CSV ({encoding}) が一致")


if __name__ == "__main__":
    check_backup(Path("public"), Path("data/raw/syukujitsu.csv"))

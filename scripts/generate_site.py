"""配信用の静的ページとアセットを準備する。"""

from pathlib import Path
from shutil import copyfile

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def generate_site(output_dir: Path) -> None:
    """テンプレート以外のソースや取得時の一時ファイルは公開対象に含めない。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "site.css", "site.js", "data-license.json"):
        copyfile(TEMPLATES / filename, output_dir / filename)
    (output_dir / ".nojekyll").write_bytes(b"")

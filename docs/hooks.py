"""MkDocs hook: builds the site's pages from the Markdown files in the project root.

README.md becomes the home page and Documentation.md the guide, so there is only one copy of each. Links between
them, which point at GitHub so they also work on PyPI, are rewritten to the site's own pages.
"""

import re
from pathlib import Path

from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/AnirudhKK/Burp-Suite-Report-Generator"
RAW_IMAGES = "https://raw.githubusercontent.com/AnirudhKK/Burp-Suite-Report-Generator/main/docs/images/"
PAGES = {
    "README.md": "index.md",
    "Documentation.md": "documentation.md",
    "CHANGELOG.md": "changelog.md",
    "SECURITY.md": "security.md",
}


def _rewrite(text: str) -> str:
    for source, page in PAGES.items():
        pattern = rf"\]\((?:{re.escape(REPO)}/blob/main/)?{re.escape(source)}(#[^)]*)?\)"
        text = re.sub(pattern, lambda m, page=page: f"]({page}{m.group(1) or ''})", text)
    text = text.replace(RAW_IMAGES, "images/").replace("](docs/images/", "](images/")
    # The site lists the sections in its sidebar, so drop the guide's hand-written contents list.
    return re.sub(r"\n## Contents\n.*?\n---\n", "\n", text, count=1, flags=re.S)


def on_files(files, config):
    for source, page in PAGES.items():
        content = _rewrite((ROOT / source).read_text(encoding="utf-8"))
        files.append(File.generated(config, page, content=content))
    return files

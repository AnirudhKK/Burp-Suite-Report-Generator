"""HTML -> PDF conversion.

Prefers a headless Chromium browser (Edge ships with Windows; Chrome/Chromium
elsewhere) because it renders the templates exactly like the HTML output.
Falls back to WeasyPrint if it is installed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_CANDIDATES_WIN = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
]
_CANDIDATES_MAC = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
_CANDIDATES_PATH = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                    "msedge", "microsoft-edge", "chrome", "brave-browser"]


def find_browser() -> str | None:
    env = os.environ.get("BURP_REPORT_BROWSER")
    if env and Path(env).is_file():
        return env
    if sys.platform == "win32":
        for c in _CANDIDATES_WIN:
            p = Path(os.path.expandvars(c))
            if p.is_file():
                return str(p)
    elif sys.platform == "darwin":
        for c in _CANDIDATES_MAC:
            if Path(c).is_file():
                return c
    for name in _CANDIDATES_PATH:
        found = shutil.which(name)
        if found:
            return found
    return None


def available_engine() -> str | None:
    if find_browser():
        return "chromium"
    try:
        import weasyprint  # noqa: F401
        return "weasyprint"
    except Exception:
        return None


def html_to_pdf(html: str, out_path: Path) -> str:
    """Write `html` to `out_path` as PDF; returns the engine used."""
    out_path = Path(out_path).resolve()
    browser = find_browser()
    if browser:
        _chromium(browser, html, out_path)
        return f"chromium ({Path(browser).stem})"
    try:
        from weasyprint import HTML
    except Exception:
        raise RuntimeError(
            "No PDF engine found. Install Microsoft Edge / Google Chrome, set BURP_REPORT_BROWSER "
            "to a Chromium-based browser executable, or `pip install weasyprint`."
        ) from None
    HTML(string=html).write_pdf(str(out_path))
    return "weasyprint"


def _chromium(browser: str, html: str, out_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="burp_report_") as tmp:
        src = Path(tmp) / "report.html"
        src.write_text(html, encoding="utf-8")
        if out_path.exists():
            out_path.unlink()
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={Path(tmp) / 'profile'}",  # isolated from any running browser instance
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={out_path}",
            src.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"Browser PDF export failed (exit {proc.returncode}): {proc.stderr.strip()[-800:]}")

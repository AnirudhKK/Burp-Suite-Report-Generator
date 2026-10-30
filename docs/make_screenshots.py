"""Regenerate the screenshots in docs/images/ from the bundled sample scan.

Run from the project root after changing the web UI or a template:

    pip install -r requirements-dev.txt
    python docs/make_screenshots.py

It starts the app, drives it in Microsoft Edge (set BURP_REPORT_TEST_BROWSER=chrome to use Chrome), and saves
PNGs that README.md and the documentation site show.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
VIEWPORT = {"width": 1440, "height": 900}


def start_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "generate_report.py", "--port", str(port), "--no-browser"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}/"
    for _ in range(80):
        try:
            urllib.request.urlopen(base)
            return proc, base
        except OSError:
            time.sleep(0.25)
    proc.kill()
    sys.exit("the app did not start")


def wait_ready(page):
    expect(page.locator("#status")).to_have_text("Up to date", timeout=20000)
    page.wait_for_timeout(600)  # let fonts and thumbnails settle


def preview_frame(page):
    return page.frame(url=lambda u: "/preview/" in u)


def open_only_panel(page, n):
    panels = page.locator("details.panel")
    for i in range(panels.count()):
        want = i == n - 1
        if (panels.nth(i).get_attribute("open") is not None) != want:
            panels.nth(i).locator("summary").click()


def scroll_preview_to(page, selector):
    # Leave room for the report's sticky search bar.
    preview_frame(page).evaluate(
        "s => scrollTo(0, document.querySelector(s).getBoundingClientRect().top + scrollY - 110)", selector
    )
    page.wait_for_timeout(400)


def save(page, name):
    path = OUT / name
    page.screenshot(path=str(path))
    Image.open(path).save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proc, base = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=os.environ.get("BURP_REPORT_TEST_BROWSER", "msedge"))
            page = browser.new_page(viewport=VIEWPORT, color_scheme="light")
            page.goto(base)
            page.click("#loadSample")
            wait_ready(page)

            # 1. The studio: template cards on the left, live preview of the corporate template on the right.
            open_only_panel(page, 1)
            save(page, "studio.png")

            # 2. The modern template, at the severity overview.
            page.click(".tcard[data-key='modern']")
            wait_ready(page)
            open_only_panel(page, 3)
            scroll_preview_to(page, "#overview")
            save(page, "template-modern.png")

            # 3. A finding's HTTP evidence with the highlighted payload, in the corporate template.
            open_only_panel(page, 1)
            page.click(".tcard[data-key='corporate']")
            wait_ready(page)
            open_only_panel(page, 7)
            scroll_preview_to(page, ".instance:has(mark.hl)")
            save(page, "finding-evidence.png")

            browser.close()
    finally:
        proc.kill()


if __name__ == "__main__":
    main()

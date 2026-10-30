"""Fixtures for the web UI tests: one app server and one Edge page shared by the whole module.

The tests in test_webui.py run in file order and build on each other's state, like a person using the app.
Set BURP_REPORT_EXE to a built .exe to test that instead of the Python source.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright not installed (pip install -r requirements-dev.txt)")
from playwright.sync_api import sync_playwright

from ..conftest import ROOT

RESULTS = ROOT / "test-results"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    port = _free_port()
    exe = os.environ.get("BURP_REPORT_EXE")
    cmd = [str(Path(exe).resolve())] if exe else [sys.executable, "generate_report.py"]
    proc = subprocess.Popen(
        [*cmd, "--port", str(port), "--no-browser"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    base = f"http://127.0.0.1:{port}/"
    for _ in range(120):  # a single-file exe needs a few seconds to unpack
        try:
            urllib.request.urlopen(base)
            break
        except OSError:
            if proc.poll() is not None:
                pytest.fail("server exited: " + proc.communicate()[0][-2000:])
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield {"base": base, "port": port}
    if os.name == "nt":  # /T also stops the child process a single-file exe starts
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.kill()
    output = proc.communicate(timeout=10)[0]
    assert "Traceback" not in output, output[-3000:]


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        # Uses the installed Microsoft Edge, so no Playwright browser download is needed.
        b = p.chromium.launch(channel=os.environ.get("BURP_REPORT_TEST_BROWSER", "msedge"))
        yield b
        b.close()


@pytest.fixture(scope="session")
def events():
    return {"console": [], "dialogs": []}


@pytest.fixture(scope="session")
def page(browser, server, events):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("console", lambda m: m.type == "error" and events["console"].append(m.text))
    pg.on("pageerror", lambda e: events["console"].append("pageerror: " + str(e)))
    pg.on("dialog", lambda d: (events["dialogs"].append(d.message), d.dismiss()) if d.type != "confirm" else None)
    pg.goto(server["base"])
    yield pg
    ctx.close()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if report.when == "call" and report.failed and "page" in item.funcargs:
        RESULTS.mkdir(exist_ok=True)
        try:
            item.funcargs["page"].screenshot(path=str(RESULTS / f"{item.name}.png"))
        except Exception:
            pass
    return report

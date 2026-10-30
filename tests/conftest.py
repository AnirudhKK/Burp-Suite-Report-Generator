from pathlib import Path

import pytest

from burp_report.config import ReportConfig
from burp_report.parser import parse_burp_xml

from . import fixtures

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "burp_report" / "samples" / "sample_burp_export.xml"
SESSION_COOKIE = "8f2a1c9e"   # the sample's session cookie value; must never survive redaction


@pytest.fixture(scope="session")
def fx(tmp_path_factory) -> Path:
    """Folder holding nasty.xml, large.xml and logo.png."""
    return fixtures.write_all(tmp_path_factory.mktemp("fx"))


@pytest.fixture(scope="session")
def sample_scan():
    return parse_burp_xml(SAMPLE)


@pytest.fixture
def cfg() -> ReportConfig:
    return ReportConfig()

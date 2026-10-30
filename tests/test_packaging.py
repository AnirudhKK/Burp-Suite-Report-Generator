"""Packaging metadata stays consistent with the code and requirements.txt."""

import re

import pytest

from burp_report import __version__
from burp_report.web import SAMPLE_XML

from .conftest import ROOT

tomllib = pytest.importorskip("tomllib", reason="tomllib needs Python 3.11+")
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _names(lines):
    return {
        re.split(r"[<>=!~\[; ]", line.strip(), maxsplit=1)[0].lower()
        for line in lines
        if line.strip() and not line.lstrip().startswith(("#", "-"))
    }


def test_dependencies_match_requirements_txt():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert _names(PYPROJECT["project"]["dependencies"]) == _names(req)


def test_console_script_points_at_cli_main():
    assert PYPROJECT["project"]["scripts"] == {"burp-report": "burp_report.cli:main"}


def test_version_is_read_from_the_package():
    assert PYPROJECT["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "burp_report.__version__"}
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_sample_ships_inside_the_package():
    assert SAMPLE_XML.is_file() and SAMPLE_XML.parent.parent == ROOT / "burp_report"


@pytest.mark.parametrize("pattern", PYPROJECT["tool"]["setuptools"]["package-data"]["burp_report"])
def test_package_data_patterns_match_files(pattern):
    assert list((ROOT / "burp_report").glob(pattern)), f"{pattern} matches nothing"


def test_pre_commit_ruff_matches_requirements_dev():
    pinned = re.search(r"^ruff==(\S+)", (ROOT / "requirements-dev.txt").read_text(encoding="utf-8"), re.M)
    hook = re.search(r"ruff-pre-commit\s+rev: v(\S+)", (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert pinned and hook and pinned.group(1) == hook.group(1)

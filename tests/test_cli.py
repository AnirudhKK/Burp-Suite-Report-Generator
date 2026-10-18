import argparse

import pytest

from burp_report import __version__
from burp_report.cli import main, parse_formats
from burp_report.pdf import available_engine

from .conftest import SAMPLE


@pytest.mark.parametrize("value, expected", [
    ("html", ["html"]), ("both", ["html", "pdf"]), ("all", ["html", "pdf", "docx"]),
    ("docx,HTML", ["html", "docx"]), (" pdf , docx ", ["pdf", "docx"]),
])
def test_parse_formats(value, expected):
    assert parse_formats(value) == expected


@pytest.mark.parametrize("value", ["exe", "html,exe", ",", ""])
def test_parse_formats_rejects(value):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_formats(value)


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"burp-report {__version__}"


def test_list_templates(capsys):
    assert main(["--list-templates"]) == 0
    out = capsys.readouterr().out
    assert all(t in out for t in ("corporate", "modern", "minimal"))


def test_batch_html_and_word(tmp_path):
    out = tmp_path / "nested" / "report"
    assert main([str(SAMPLE), "-y", "-f", "html,docx", "-t", "modern", "--client", "Acme", "-o", str(out)]) == 0
    html = out.with_suffix(".html").read_text(encoding="utf-8")
    assert "Acme" in html and "--accent-2" in html
    assert out.with_suffix(".docx").read_bytes()[:2] == b"PK"


@pytest.mark.skipif(available_engine() is None, reason="no Edge/Chrome or WeasyPrint for PDF output")
def test_batch_pdf(tmp_path):
    assert main([str(SAMPLE), "-y", "-f", "pdf", "-o", str(tmp_path / "r")]) == 0
    data = (tmp_path / "r.pdf").read_bytes()
    assert data[:5] == b"%PDF-" and len(data) > 20_000


def test_min_severity(tmp_path):
    assert main([str(SAMPLE), "-y", "--min-severity", "High", "-o", str(tmp_path / "r")]) == 0
    assert (tmp_path / "r.html").read_text(encoding="utf-8").count('<article class="finding') == 2


def test_export_template_then_use_it(tmp_path):
    dest = tmp_path / "mine"
    assert main(["--export-template", "corporate", str(dest)]) == 0
    assert (dest / "report.html.j2").exists() and (dest / "base.css").exists()
    assert main(["--export-template", "corporate", str(dest)]) == 2, "must not overwrite an existing template"
    assert main([str(SAMPLE), "-y", "-t", str(dest), "-o", str(tmp_path / "r")]) == 0
    assert (tmp_path / "r.html").exists()


def test_bad_inputs(tmp_path):
    (tmp_path / "bad.xml").write_text("<foo/>", encoding="utf-8")
    assert main([str(tmp_path / "bad.xml"), "-y", "-o", str(tmp_path / "r")]) == 1
    assert main([str(SAMPLE), "-y", "-p", str(tmp_path / "missing.json")]) == 2
    assert main(["-y"]) == 2

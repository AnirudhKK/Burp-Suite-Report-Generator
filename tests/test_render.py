import io
import re
import zipfile

import pytest

from burp_report.parser import parse_burp_xml
from burp_report.render import build_context, list_templates, render_html

from .conftest import SESSION_COOKIE

TEMPLATES = [t.key for t in list_templates()]


def test_builtin_templates():
    assert TEMPLATES == ["corporate", "minimal", "modern"]


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_renders(sample_scan, cfg, template):
    cfg.template = template
    html = render_html(sample_scan, cfg)
    assert html.lower().startswith("<!doctype html>")
    assert "Web Application Security Assessment" in html
    assert html.count('<article class="finding') == 8
    assert "@font-face" in html and "data:font/woff2;base64," in html
    assert 'id="owasp"' in html
    missing = {a for a in re.findall(r'href="#([^"]+)"', html) if f'id="{a}"' not in html}
    assert not missing, f"dangling anchors: {missing}"


def test_user_text_is_escaped(sample_scan, cfg):
    cfg.client = "<img src=x onerror=alert(1)>"
    cfg.classification = "</style><script>alert(3)</script>"
    html = render_html(sample_scan, cfg)
    assert "<img src=x" not in html and "<script>alert(3)" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_redaction_on_by_default(sample_scan, cfg):
    html = render_html(sample_scan, cfg)
    assert SESSION_COOKIE not in html and "[REDACTED]" in html
    cfg.redact_secrets = False
    assert SESSION_COOKIE in render_html(sample_scan, cfg)


def test_payload_highlighting_toggle(sample_scan, cfg):
    assert '<mark class="hl">' in render_html(sample_scan, cfg)
    cfg.highlight_payloads = False
    assert '<mark class="hl">' not in render_html(sample_scan, cfg)


def test_owasp_2025_by_default(sample_scan, cfg):
    owasp = build_context(sample_scan, cfg)["owasp"]
    rows = {r["code"]: r for r in owasp["rows"]}
    assert owasp["edition"] == "OWASP Top 10:2025" and len(rows) == 10
    assert len(rows["A05"]["findings"]) == 2  # XSS + SQL injection
    assert rows["A05"]["name"] == "Injection"
    html = render_html(sample_scan, cfg)
    assert "OWASP Top 10:2025 mapping</h2>" in html and "A05:2025</span> Injection" in html
    assert ":2021" not in html


def test_owasp_2021_on_request(sample_scan, cfg):
    cfg.owasp_edition = "2021"
    owasp = build_context(sample_scan, cfg)["owasp"]
    rows = {r["code"]: r for r in owasp["rows"]}
    assert owasp["edition"] == "OWASP Top 10:2021"
    assert len(rows["A03"]["findings"]) == 2 and rows["A03"]["name"] == "Injection"
    html = render_html(sample_scan, cfg)
    assert "OWASP Top 10:2021 mapping</h2>" in html and "A03:2021</span> Injection" in html
    assert ":2025" not in html


def test_sections_and_filters(sample_scan, cfg):
    cfg.sections["owasp_table"] = False
    cfg.severities = ["High"]
    html = render_html(sample_scan, cfg)
    assert 'id="owasp"' not in html
    assert html.count('<article class="finding') == 2


def test_per_instance_grouping(sample_scan, cfg):
    cfg.group_by_type = False
    assert render_html(sample_scan, cfg).count('<article class="finding') == 11


def test_nasty_export_renders(fx, cfg):
    html = render_html(parse_burp_xml(fx / "nasty.xml"), cfg)
    assert "<script>alert('n')</script>" not in html
    assert "&lt;script&gt;alert(&#39;n&#39;)&lt;/script&gt;" in html
    assert "日本語" in html and "binary body omitted" in html and "(truncated)" in html.lower()


def test_word_export(sample_scan, cfg):
    from burp_report.docx_export import DOCX_AVAILABLE, render_docx

    if not DOCX_AVAILABLE:
        pytest.skip("python-docx not installed")
    data = render_docx(sample_scan, cfg)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    for needle in (
        "OWASP Top 10:2025 mapping",
        "A05:2025 Injection",
        "[REDACTED]",
        'w:highlight w:val="yellow"',
        "CWE-79",
        "TOC \\o",
    ):
        assert needle in xml, needle
    assert SESSION_COOKIE not in xml


def test_word_export_2021(sample_scan, cfg):
    from burp_report.docx_export import DOCX_AVAILABLE, render_docx

    if not DOCX_AVAILABLE:
        pytest.skip("python-docx not installed")
    cfg.owasp_edition = "2021"
    with zipfile.ZipFile(io.BytesIO(render_docx(sample_scan, cfg))) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "OWASP Top 10:2021 mapping" in xml and "A03:2021 Injection" in xml and ":2025" not in xml

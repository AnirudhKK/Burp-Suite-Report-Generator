import pytest

from burp_report.parser import parse_burp_bytes

from . import fixtures


def test_sample_export(sample_scan):
    assert len(sample_scan.issues) == 11
    assert sample_scan.hosts == ["https://api.example.com", "https://shop.example.com"]
    xss = sample_scan.issues[0]
    assert xss.name == "Cross-site scripting (reflected)" and xss.severity == "High"
    assert xss.evidence and xss.evidence[0].request.startswith("GET ")


def test_severity_and_confidence_aliases_are_normalised():
    scan = parse_burp_bytes(fixtures.nasty_xml().encode(), "nasty.xml")
    got = {i.name: (i.severity, i.confidence) for i in scan.issues}
    assert got["Cross-site scripting [DOM-based]"] == ("High", "Certain")
    assert got["Name with <script>alert('n')</script> & ampersand"] == ("High", "Firm")
    assert got["Informational with alias severity"] == ("Information", "Firm")
    assert got["False positive marked in Burp"][0] == "False positive"


def test_unicode_host_and_missing_host():
    scan = parse_burp_bytes(fixtures.nasty_xml().encode(), "nasty.xml")
    assert "https://bücher.example" in scan.hosts
    assert next(i for i in scan.issues if i.name == "Missing host element").host == ""


def test_binary_body_is_replaced_by_a_note():
    scan = parse_burp_bytes(fixtures.nasty_xml().encode(), "nasty.xml")
    resp = next(i for i in scan.issues if i.name == "Binary response body").evidence[0].response
    assert resp.endswith("[binary body omitted: 3400 bytes, image/png]")
    assert "\x89PNG" not in resp


@pytest.mark.parametrize("data, message", [
    (b"<foo/>", "Expected a Burp <issues> export"),
    (b"not xml", "Not a valid XML file"),
])
def test_rejects_non_burp_files(data, message):
    with pytest.raises(ValueError, match=message):
        parse_burp_bytes(data, "x.xml")


def test_external_entities_are_not_resolved():
    xxe = (b'<?xml version="1.0"?><!DOCTYPE issues [<!ENTITY x SYSTEM "file:///c:/windows/win.ini">]>'
           b"<issues><issue><name>&x;</name></issue></issues>")
    with pytest.raises(ValueError):
        parse_burp_bytes(xxe, "xxe.xml")

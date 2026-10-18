import pytest

from burp_report.owasp import OWASP_2021, categories, parse_cwes


def test_parse_cwes_from_burp_html():
    html = ('<ul><li><a href="https://cwe.mitre.org/data/definitions/79.html">CWE-79: Improper Neutralization of '
            'Input During Web Page Generation</a></li><li>CWE-116: Improper Encoding &amp; Escaping</li>'
            '<li>CWE-79: duplicate</li></ul>')
    assert parse_cwes(html) == [(79, "Improper Neutralization of Input During Web Page Generation"),
                                (116, "Improper Encoding & Escaping")]


def test_parse_cwes_handles_empty():
    assert parse_cwes("") == [] and parse_cwes(None) == []


@pytest.mark.parametrize("cwe, code", [(79, "A03"), (89, "A03"), (942, "A05"), (523, "A02"), (352, "A01")])
def test_known_mappings(cwe, code):
    assert [c for c, _ in categories([cwe])] == [code]


def test_unmapped_cwe():
    assert categories([1]) == []


def test_table_is_complete():
    assert list(OWASP_2021) == [f"A{n:02}" for n in range(1, 11)]
    assert all(cwes for _, cwes in OWASP_2021.values())

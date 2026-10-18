import pytest

from burp_report.owasp import DEFAULT_EDITION, EDITIONS, OWASP_2021, OWASP_2025, categories, edition_label, parse_cwes


def test_parse_cwes_from_burp_html():
    html = ('<ul><li><a href="https://cwe.mitre.org/data/definitions/79.html">CWE-79: Improper Neutralization of '
            'Input During Web Page Generation</a></li><li>CWE-116: Improper Encoding &amp; Escaping</li>'
            '<li>CWE-79: duplicate</li></ul>')
    assert parse_cwes(html) == [(79, "Improper Neutralization of Input During Web Page Generation"),
                                (116, "Improper Encoding & Escaping")]


def test_parse_cwes_handles_empty():
    assert parse_cwes("") == [] and parse_cwes(None) == []


def test_2025_is_the_default():
    assert DEFAULT_EDITION == "2025" and list(EDITIONS) == ["2025", "2021"]
    assert categories([79]) == [("A05", "Injection")]
    assert edition_label("2025") == "OWASP Top 10:2025"


@pytest.mark.parametrize("cwe, code", [
    (79, "A05"), (89, "A05"), (942, "A02"), (523, "A04"), (352, "A01"), (918, "A01"),   # SSRF merged into A01
    (1104, "A03"), (755, "A10"), (209, "A10"), (778, "A09"), (502, "A08"), (798, "A07"), (434, "A06"),
])
def test_known_2025_mappings(cwe, code):
    assert [c for c, _ in categories([cwe], "2025")] == [code]


@pytest.mark.parametrize("cwe, code", [(79, "A03"), (89, "A03"), (942, "A05"), (523, "A02"), (352, "A01"), (918, "A10")])
def test_known_2021_mappings(cwe, code):
    assert [c for c, _ in categories([cwe], "2021")] == [code]


def test_unmapped_cwe():
    assert categories([1]) == [] and categories([1], "2021") == []


def test_several_categories_in_order():
    assert [c for c, _ in categories([755, 79, 942], "2025")] == ["A02", "A05", "A10"]


@pytest.mark.parametrize("table, sizes", [
    # CWE counts OWASP publishes for each category ("CWEs Mapped")
    (OWASP_2025, [40, 16, 6, 32, 37, 39, 36, 14, 5, 24]),
    (OWASP_2021, [34, 30, 33, 40, 20, 3, 22, 10, 4, 1]),
])
def test_tables_are_complete(table, sizes):
    assert list(table) == [f"A{n:02}" for n in range(1, 11)]
    assert [len(cwes) for _, cwes in table.values()] == sizes


def test_2025_category_names():
    assert [name for name, _ in OWASP_2025.values()] == [
        "Broken Access Control", "Security Misconfiguration", "Software Supply Chain Failures",
        "Cryptographic Failures", "Injection", "Insecure Design", "Authentication Failures",
        "Software or Data Integrity Failures", "Security Logging & Alerting Failures",
        "Mishandling of Exceptional Conditions"]

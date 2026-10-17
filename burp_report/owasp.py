"""CWE → OWASP Top 10 (2021) mapping, bundled so it works offline.

The CWE lists are the ones OWASP publishes for each 2021 category ("List of Mapped CWEs").
Burp's export already names the CWEs for each issue, so no lookup service is needed.
"""
from __future__ import annotations

import html
import re

EDITION = "OWASP Top 10 (2021)"

OWASP_2021: dict[str, tuple[str, frozenset[int]]] = {
    "A01": ("Broken Access Control", frozenset({
        22, 23, 35, 59, 200, 201, 219, 264, 275, 276, 284, 285, 352, 359, 377, 402, 425, 441, 497, 538, 540,
        548, 552, 566, 601, 639, 651, 668, 706, 862, 863, 913, 922, 1275})),
    "A02": ("Cryptographic Failures", frozenset({
        259, 261, 296, 310, 319, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 335, 336, 337, 338,
        340, 347, 523, 720, 757, 759, 760, 780, 818, 916})),
    "A03": ("Injection", frozenset({
        20, 74, 75, 77, 78, 79, 80, 83, 87, 88, 89, 90, 91, 93, 94, 95, 96, 97, 98, 99, 100, 113, 116, 138,
        184, 470, 471, 564, 610, 643, 644, 652, 917})),
    "A04": ("Insecure Design", frozenset({
        73, 183, 209, 213, 235, 256, 257, 266, 269, 280, 311, 312, 313, 316, 419, 430, 434, 444, 451, 472,
        501, 522, 525, 539, 579, 598, 602, 642, 646, 650, 653, 656, 657, 799, 807, 840, 841, 927, 1021,
        1173})),
    "A05": ("Security Misconfiguration", frozenset({
        2, 11, 13, 15, 16, 260, 315, 520, 526, 537, 541, 547, 611, 614, 756, 776, 942, 1004, 1032, 1174})),
    "A06": ("Vulnerable and Outdated Components", frozenset({937, 1035, 1104})),
    "A07": ("Identification and Authentication Failures", frozenset({
        255, 259, 287, 288, 290, 294, 295, 297, 300, 302, 304, 306, 307, 346, 384, 521, 613, 620, 640, 798,
        940, 1216})),
    "A08": ("Software and Data Integrity Failures", frozenset({345, 353, 426, 494, 502, 565, 784, 829, 830, 915})),
    "A09": ("Security Logging and Monitoring Failures", frozenset({117, 223, 532, 778})),
    "A10": ("Server-Side Request Forgery (SSRF)", frozenset({918})),
}

_CWE = re.compile(r"CWE-(\d{1,5})(?:\s*:\s*([^<\n]+))?")
_TAGS = re.compile(r"<[^>]+>")


def parse_cwes(classifications_html: str) -> list[tuple[int, str]]:
    """CWE ids and titles from Burp's <vulnerabilityClassifications> HTML, in order, without duplicates."""
    seen: dict[int, str] = {}
    for line in re.split(r"</li>|<br\s*/?>|\n", classifications_html or "", flags=re.I):
        text = _TAGS.sub("", line)
        for m in _CWE.finditer(text):
            seen.setdefault(int(m.group(1)), html.unescape(m.group(2) or "").strip())
    return list(seen.items())


def categories(cwe_ids: list[int]) -> list[tuple[str, str]]:
    """OWASP categories (code, name) that any of the CWEs map to, in category order."""
    ids = set(cwe_ids)
    return [(code, name) for code, (name, mapped) in OWASP_2021.items() if ids & mapped]

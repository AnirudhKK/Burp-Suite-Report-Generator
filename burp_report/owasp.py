"""CWE → OWASP Top 10 mapping (2025 and 2021 editions), bundled so it works offline.

The CWE lists are the ones OWASP publishes for each category ("List of Mapped CWEs"):
https://top10.owasp.org/2025/ and https://owasp.org/Top10/2021/ (sources: github.com/OWASP/Top10).
Burp's export already names the CWEs for each issue, so no lookup service is needed.
"""
from __future__ import annotations

import html
import re

OWASP_2025: dict[str, tuple[str, frozenset[int]]] = {
    "A01": ("Broken Access Control", frozenset({
        22, 23, 36, 59, 61, 65, 200, 201, 219, 276, 281, 282, 283, 284, 285, 352, 359, 377, 379, 402, 424, 425,
        441, 497, 538, 540, 548, 552, 566, 601, 615, 639, 668, 732, 749, 862, 863, 918, 922, 1275})),
    "A02": ("Security Misconfiguration", frozenset({
        5, 11, 13, 15, 16, 260, 315, 489, 526, 547, 611, 614, 776, 942, 1004, 1174})),
    "A03": ("Software Supply Chain Failures", frozenset({447, 1035, 1104, 1329, 1357, 1395})),
    "A04": ("Cryptographic Failures", frozenset({
        261, 296, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 334, 335, 336, 337, 338,
        340, 342, 347, 523, 757, 759, 760, 780, 916, 1240, 1241})),
    "A05": ("Injection", frozenset({
        20, 74, 76, 77, 78, 79, 80, 83, 86, 88, 89, 90, 91, 93, 94, 95, 96, 97, 98, 99, 103, 104, 112, 113, 114,
        115, 116, 129, 159, 470, 493, 500, 564, 610, 643, 644, 917})),
    "A06": ("Insecure Design", frozenset({
        73, 183, 256, 266, 269, 286, 311, 312, 313, 316, 362, 382, 419, 434, 436, 444, 451, 454, 472, 501, 522,
        525, 539, 598, 602, 628, 642, 646, 653, 656, 657, 676, 693, 799, 807, 841, 1021, 1022, 1125})),
    "A07": ("Authentication Failures", frozenset({
        258, 259, 287, 288, 289, 290, 291, 293, 294, 295, 297, 298, 299, 300, 302, 303, 304, 305, 306, 307, 308,
        309, 346, 350, 384, 521, 613, 620, 640, 798, 940, 941, 1390, 1391, 1392, 1393})),
    "A08": ("Software or Data Integrity Failures", frozenset({
        345, 353, 426, 427, 494, 502, 506, 509, 565, 784, 829, 830, 915, 926})),
    "A09": ("Security Logging & Alerting Failures", frozenset({117, 221, 223, 532, 778})),
    "A10": ("Mishandling of Exceptional Conditions", frozenset({
        209, 215, 234, 235, 248, 252, 274, 280, 369, 390, 391, 394, 396, 397, 460, 476, 478, 484, 550, 636, 703,
        754, 755, 756})),
}

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

EDITIONS = {"2025": OWASP_2025, "2021": OWASP_2021}
DEFAULT_EDITION = "2025"


def edition_label(edition: str) -> str:
    return f"OWASP Top 10:{edition}"   # OWASP's own naming, e.g. "OWASP Top 10:2025"


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


def categories(cwe_ids: list[int], edition: str = DEFAULT_EDITION) -> list[tuple[str, str]]:
    """OWASP categories (code, name) of the given edition that any of the CWEs map to, in category order."""
    ids = set(cwe_ids)
    return [(code, name) for code, (name, mapped) in EDITIONS[edition].items() if ids & mapped]

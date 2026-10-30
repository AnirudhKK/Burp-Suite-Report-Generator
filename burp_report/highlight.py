"""Find the payloads Burp names in an issue's detail and mark where they appear in the HTTP evidence.

Burp writes e.g. "The payload <b>abc<script>alert(1)</script>xyz</b> was submitted in the q parameter".
The payload usually appears URL-encoded in the request and raw (or HTML-encoded) in the response, so each
character may match in any of its common encodings.
"""

from __future__ import annotations

import html
import re

from markupsafe import Markup, escape

_BOLD = re.compile(r"<(b|strong)\b[^>]*>(.*?)</\1\s*>", re.I | re.S)
_LI = re.compile(r"<li\b[^>]*>(.*?)</li\s*>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_PAYLOAD_CONTEXT = re.compile(r"(payload|submitted|injected|origin|string|expression|value)\W*$", re.I)
_SPECIAL = re.compile(r"[^\w\s]")

_ALTERNATES = {
    "<": ["&lt;", "&#60;", "&#x3c;", "\\u003c"],
    ">": ["&gt;", "&#62;", "&#x3e;", "\\u003e"],
    '"': ["&quot;", "&#34;", "&#x22;", "\\u0022", '\\"'],
    "'": ["&#39;", "&#x27;", "&apos;", "\\u0027"],
    "&": ["&amp;", "\\u0026"],
    "/": ["\\/"],
    " ": ["+"],
}
MAX_CANDIDATES = 8
MAX_LEN = 300
MAX_MARKS = 60


def _plain(fragment: str) -> str:
    return html.unescape(_TAGS.sub("", fragment)).strip()


def candidates(issue_detail: str, detail_items: list[str] | None = None) -> list[str]:
    """Strings worth highlighting: named payloads, and distinctive values such as origins or e-mail addresses."""
    found: list[str] = []
    detail = issue_detail or ""
    for m in _BOLD.finditer(detail):
        text = _plain(m.group(2))
        before = _plain(detail[max(0, m.start() - 60) : m.start()])
        if not text or len(text) > MAX_LEN:
            continue
        if _PAYLOAD_CONTEXT.search(before) or (len(text) >= 6 and _SPECIAL.search(text)):
            found.append(text)
    items = [_plain(i) for i in _LI.findall(detail)] + [_plain(i) for i in detail_items or []]
    found += [t for t in items if 4 <= len(t) <= MAX_LEN and not re.search(r"\s", t) and _SPECIAL.search(t)]
    out: list[str] = []
    for t in found:
        if t not in out:
            out.append(t)
    return out[:MAX_CANDIDATES]


def _char_pattern(ch: str) -> str:
    if ch.isalnum() or ch == "_":
        return re.escape(ch)
    alts = [re.escape(ch)] + [re.escape(a) for a in _ALTERNATES.get(ch, [])]
    pct = "".join(f"%{b:02x}" for b in ch.encode("utf-8"))
    alts.append(f"(?i:{re.escape(pct)})")
    for ent in (f"&#{ord(ch)};", f"&#x{ord(ch):x};"):
        if ent not in _ALTERNATES.get(ch, []):
            alts.append(f"(?i:{re.escape(ent)})")
    return "(?:" + "|".join(alts) + ")"


def compile_candidates(texts: list[str]) -> list[re.Pattern]:
    return [re.compile("".join(_char_pattern(c) for c in t)) for t in texts]


def spans(text: str, patterns: list[re.Pattern]) -> list[tuple[int, int]]:
    """Merged, sorted (start, end) ranges of every match."""
    found = []
    for p in patterns:
        for m in p.finditer(text):
            if m.end() > m.start():
                found.append((m.start(), m.end()))
            if len(found) >= MAX_MARKS:
                break
    found.sort()
    merged: list[tuple[int, int]] = []
    for s, e in found:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged


def to_markup(text: str, marks: list[tuple[int, int]]) -> Markup:
    out, pos = [], 0
    for s, e in marks:
        out.append(escape(text[pos:s]))
        out.append(Markup('<mark class="hl">') + escape(text[s:e]) + Markup("</mark>"))
        pos = e
    out.append(escape(text[pos:]))
    return Markup("").join(out)

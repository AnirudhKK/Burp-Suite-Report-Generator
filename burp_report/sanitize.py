"""Allow-list HTML sanitizer for the HTML fragments Burp embeds in its XML.

Issue details can echo content from the scanned target, so nothing outside a
small set of formatting tags and safe link targets is passed through.
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li", "a", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td",
    "span", "div", "blockquote", "sub", "sup", "hr",
}
VOID_TAGS = {"br", "hr"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "template", "noscript"}
SAFE_SCHEMES = ("http://", "https://", "mailto:")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.strip().lower().startswith(SAFE_SCHEMES):
                self.out.append(f'<a href="{escape(href.strip())}" target="_blank" rel="noopener noreferrer">')
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{tag}>")
        if tag not in VOID_TAGS:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS and not self.skip_depth:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth or tag not in self.open:
            return
        while self.open:
            t = self.open.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        self.close()
        return "".join(self.out) + "".join(f"</{t}>" for t in reversed(self.open))


def sanitize_html(fragment: str) -> str:
    if not fragment:
        return ""
    s = _Sanitizer()
    s.feed(fragment)
    return s.result()

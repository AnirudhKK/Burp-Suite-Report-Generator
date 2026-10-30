"""Mask secrets (session cookies, auth headers, tokens, passwords, keys) in HTTP evidence.

Only the report output is changed; the loaded scan keeps the original data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MASK = "[REDACTED]"

# Parameter / JSON key / header names whose values are treated as secret.
_SENSITIVE_NAME = re.compile(
    r"passw(?:or)?d|passphrase|^pass$|^pwd$|secret|token|api[-_]?key|access[-_]?key|private[-_]?key|"
    r"^auth$|^auth[-_]|[-_]auth$|authoriz|credential|session|sessid|^sid$|csrf|xsrf|jwt|^otp$|signature|^sig$",
    re.I,
)
# Headers that contain those words but carry no secret.
_HEADER_ALLOW = re.compile(r"^(www-authenticate|proxy-authenticate|access-control-|sec-websocket-protocol)", re.I)

_HEADER_LINE = re.compile(r"^([A-Za-z0-9!#$%&'*+.^_`|~-]+):[ \t]*(.*)$")
# The key class excludes ? & ; and whitespace, so the leftmost match starts right after one of them.
_PARAM = re.compile(r"(?P<pre>(?P<key>[A-Za-z0-9_.\-\[\]]{1,64})=)(?P<val>[^&\s#;\"'<>]+)")
# Cheap pre-check: the name-based rules can only fire if one of these appears somewhere in the text.
# (Substring checks on lowercased text; a case-insensitive regex alternation is ~20x slower on long bodies.)
_NAME_HINTS = (
    "pass",
    "pwd",
    "secret",
    "token",
    "key",
    "auth",
    "credential",
    "sess",
    "sid",
    "csrf",
    "xsrf",
    "jwt",
    "otp",
    "sig",
)
_JSON = re.compile(r'(?P<pre>"(?P<key>[^"\\]{1,64})"\s*:\s*")(?P<val>(?:[^"\\]|\\.)+)(?=")')
_HTML_INPUT = re.compile(
    r"(?P<pre><input\b[^>]*?\bname\s*=\s*[\"'](?P<key>[^\"']{1,64})[\"'][^>]*?\bvalue\s*=\s*[\"'])(?P<val>[^\"']+)",
    re.I,
)
_TOKEN_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"),  # JWT
    # AWS access key id, GitHub token, Slack token, Google API key (one pass over the text)
    re.compile(
        r"\b(?:(?:AKIA|ASIA)[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|xox[abprs]-[A-Za-z0-9-]{10,}"
        r"|AIza[0-9A-Za-z_-]{35})\b"
    ),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]


@dataclass
class Redactor:
    """Applies the built-in rules (if enabled) and the user's extra values/patterns."""

    builtin: bool = True
    custom: list[re.Pattern] = field(default_factory=list)
    count: int = 0

    @classmethod
    def from_config(cls, enabled: bool, custom_lines: list[str]) -> Redactor:
        return cls(builtin=enabled, custom=compile_custom(custom_lines))

    @property
    def active(self) -> bool:
        return self.builtin or bool(self.custom)

    def _sub(self, pattern: re.Pattern, text: str, keep_prefix: bool = False, check_key: bool = False) -> str:
        def repl(m: re.Match) -> str:
            already = m.groupdict().get("val", m.group(0)) == MASK
            if already or not m.group(0) or (check_key and not _SENSITIVE_NAME.search(m.group("key"))):
                return m.group(0)
            self.count += 1
            return (m.group("pre") if keep_prefix else "") + MASK

        return pattern.sub(repl, text)

    def message(self, text: str) -> str:
        """Redact a raw HTTP request or response."""
        if not text or not self.active:
            return text
        if self.builtin:
            head, sep, body = text.partition("\n\n")
            head = "\n".join(self._header(line) if n else line for n, line in enumerate(head.split("\n")))
            text = head + sep + body
            text = self.text(text, custom=False)
        for pattern in self.custom:
            text = self._sub(pattern, text)
        return text

    def text(self, text: str, custom: bool = True) -> str:
        """Redact free text such as a URL (no header handling)."""
        if not text or not self.active:
            return text
        if self.builtin:
            low = text.lower()
            if any(h in low for h in _NAME_HINTS):
                for pattern in (_PARAM, _JSON, _HTML_INPUT):
                    text = self._sub(pattern, text, keep_prefix=True, check_key=True)
            for pattern in _TOKEN_PATTERNS:
                text = self._sub(pattern, text)
        if custom:
            for pattern in self.custom:
                text = self._sub(pattern, text)
        return text

    def _header(self, line: str) -> str:
        m = _HEADER_LINE.match(line)
        if not m:
            return line
        name, value = m.group(1), m.group(2)
        lname = name.lower()
        if lname == "cookie":
            parts = []
            for c in value.split(";"):
                k, eq, v = c.partition("=")
                if eq and v.strip():
                    self.count += v.strip() != MASK
                    parts.append(f"{k}={MASK}")
                else:
                    parts.append(c)
            return f"{name}: {';'.join(parts)}"
        if lname == "set-cookie":
            first, semi, attrs = value.partition(";")
            k, eq, v = first.partition("=")
            if eq and v.strip():
                self.count += v.strip() != MASK
                return f"{name}: {k}={MASK}{semi}{attrs}"
            return line
        if lname in ("authorization", "proxy-authorization"):
            scheme, _, cred = value.partition(" ")
            self.count += (cred or scheme).strip() != MASK
            return f"{name}: {scheme} {MASK}" if cred else f"{name}: {MASK}"
        if _SENSITIVE_NAME.search(name) and not _HEADER_ALLOW.match(name) and value.strip():
            self.count += value.strip() != MASK
            return f"{name}: {MASK}"
        return line


def compile_custom(lines: list[str]) -> list[re.Pattern]:
    """Each line is literal text to mask, or /regex/ (optionally /regex/i)."""
    out = []
    for raw in lines or []:
        line = raw.strip()
        if not line:
            continue
        m = re.fullmatch(r"/(.+)/(i?)", line)
        if m:
            try:
                out.append(re.compile(m.group(1), re.I if m.group(2) else 0))
            except re.error as exc:
                raise ValueError(f"Invalid redaction pattern {line}: {exc}") from exc
        else:
            out.append(re.compile(re.escape(line)))
    return out

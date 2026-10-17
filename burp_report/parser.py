"""Parse Burp Suite Professional XML issue exports."""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

SEVERITIES = ["High", "Medium", "Low", "Information", "False positive"]
CONFIDENCES = ["Certain", "Firm", "Tentative"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}
_SEVERITY_ALIASES = {s.lower(): s for s in SEVERITIES} | {"info": "Information", "informational": "Information",
                                                         "false-positive": "False positive", "falsepositive": "False positive"}
_CONFIDENCE_ALIASES = {c.lower(): c for c in CONFIDENCES}
_BINARY_TYPES = ("image/", "font/", "audio/", "video/", "application/octet-stream", "application/pdf",
                 "application/zip", "application/x-shockwave-flash", "application/font", "application/vnd.")
CONFIDENCE_RANK = {c: i for i, c in enumerate(CONFIDENCES)}


@dataclass
class Evidence:
    request: str = ""
    response: str = ""
    method: str = ""
    redirected: bool = False


@dataclass
class Issue:
    serial: str
    type_id: str
    name: str
    host: str
    ip: str
    path: str
    location: str
    severity: str
    confidence: str
    issue_background: str = ""
    remediation_background: str = ""
    references: str = ""
    classifications: str = ""
    issue_detail: str = ""
    detail_items: list[str] = field(default_factory=list)
    remediation_detail: str = ""
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def url(self) -> str:
        return self.host.rstrip("/") + self.path


@dataclass
class ScanReport:
    source: Path
    burp_version: str
    export_time: str
    issues: list[Issue]

    @property
    def hosts(self) -> list[str]:
        return sorted({i.host for i in self.issues})

    @property
    def issue_names(self) -> list[str]:
        return sorted({i.name for i in self.issues})


def _text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _decode(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    text = el.text
    if el.get("base64", "").lower() == "true":
        try:
            data = base64.b64decode(text)
        except ValueError:
            data = None
        if data is not None:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin-1")
    return _strip_binary_body(text.replace("\r\n", "\n"))


def _strip_binary_body(message: str) -> str:
    """Replace binary HTTP bodies (images, fonts, archives...) with a short placeholder."""
    head, sep, body = message.partition("\n\n")
    if not sep or not body:
        return message
    ctype = ""
    for line in head.split("\n")[1:]:
        if line.lower().startswith("content-type:"):
            ctype = line.split(":", 1)[1].strip().lower()
            break
    sample = body[:2048]
    controls = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\t\n\r")
    binary_type = ctype.startswith(_BINARY_TYPES) and not ctype.split(";")[0].endswith(("+xml", "json", "svg"))
    if binary_type or "\x00" in sample or controls > len(sample) * 0.1:
        return f"{head}\n\n[binary body omitted: {len(body)} bytes{', ' + ctype if ctype else ''}]"
    return message


def _norm(value: str, aliases: dict[str, str], default: str) -> str:
    value = value.strip()
    return aliases.get(value.lower(), value or default)


def parse_burp_xml(path: str | Path) -> ScanReport:
    path = Path(path)
    return parse_burp_bytes(path.read_bytes(), path)


def parse_burp_bytes(data: bytes, source: str | Path = "report.xml") -> ScanReport:
    path = Path(source)
    # ElementTree never resolves external entities, so Burp's inline DTD is safe to parse.
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Not a valid XML file: {exc}") from exc
    if root.tag != "issues":
        raise ValueError(f"Expected a Burp <issues> export, found <{root.tag}>")

    issues: list[Issue] = []
    for el in root.findall("issue"):
        host_el = el.find("host")
        evidence = []
        for rr in el.findall("requestresponse"):
            req = rr.find("request")
            evidence.append(Evidence(
                request=_decode(req),
                response=_decode(rr.find("response")),
                method=req.get("method", "") if req is not None else "",
                redirected=_text(rr, "responseRedirected").lower() == "true",
            ))
        issues.append(Issue(
            serial=_text(el, "serialNumber"),
            type_id=_text(el, "type"),
            name=_text(el, "name") or "Unnamed issue",
            host=(host_el.text or "").strip() if host_el is not None else "",
            ip=host_el.get("ip", "") if host_el is not None else "",
            path=_text(el, "path"),
            location=_text(el, "location"),
            severity=_norm(_text(el, "severity"), _SEVERITY_ALIASES, "Information"),
            confidence=_norm(_text(el, "confidence"), _CONFIDENCE_ALIASES, "Tentative"),
            issue_background=_text(el, "issueBackground"),
            remediation_background=_text(el, "remediationBackground"),
            references=_text(el, "references"),
            classifications=_text(el, "vulnerabilityClassifications"),
            issue_detail=_text(el, "issueDetail"),
            detail_items=[(d.text or "").strip() for d in el.findall("issueDetailItems/issueDetailItem")],
            remediation_detail=_text(el, "remediationDetail"),
            evidence=evidence,
        ))

    return ScanReport(
        source=path,
        burp_version=root.get("burpVersion", ""),
        export_time=root.get("exportTime", ""),
        issues=issues,
    )

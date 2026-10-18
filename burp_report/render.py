"""Turn a parsed scan + ReportConfig into report HTML using a Jinja2 template."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from . import highlight
from .config import ReportConfig
from .owasp import EDITIONS as OWASP_EDITIONS, categories, edition_label, parse_cwes
from .parser import CONFIDENCE_RANK, SEVERITIES, SEVERITY_RANK, Issue, ScanReport
from .redact import Redactor
from .sanitize import sanitize_html

TEMPLATES_DIR = Path(__file__).parent / "templates"
COMMON_DIR = TEMPLATES_DIR / "_common"
FONTS_DIR = Path(__file__).parent / "fonts"

# Open-licensed (SIL OFL) variable fonts shipped with the tool, Latin subset. They are embedded
# as data URIs so exported HTML and PDF look identical on every machine, even offline.
# Characters outside the subset fall back to the next font in the stack.
BUNDLED_FONTS = {
    "Inter": ("inter.woff2", "100 900"),
    "Source Sans 3": ("source-sans-3.woff2", "200 900"),
    "Source Serif 4": ("source-serif-4.woff2", "200 900"),
    "IBM Plex Sans": ("ibm-plex-sans.woff2", "100 700"),
    "JetBrains Mono": ("jetbrains-mono.woff2", "100 800"),
}
SEVERITY_ORDER = [s for s in SEVERITIES if s != "False positive"] + ["False positive"]


# ---------------------------------------------------------------- templates

@dataclass
class TemplateInfo:
    key: str
    name: str
    description: str
    path: Path


def list_templates() -> list[TemplateInfo]:
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "report.html.j2").exists():
            out.append(_template_info(d))
    return out


def _template_info(d: Path) -> TemplateInfo:
    meta = {}
    if (d / "template.json").exists():
        meta = json.loads((d / "template.json").read_text(encoding="utf-8"))
    return TemplateInfo(d.name, meta.get("name", d.name), meta.get("description", ""), d)


def resolve_template(name_or_path: str) -> Path:
    builtin = TEMPLATES_DIR / name_or_path
    if (builtin / "report.html.j2").exists() and not name_or_path.startswith("_"):
        return builtin
    custom = Path(name_or_path).expanduser()
    if (custom / "report.html.j2").exists():
        return custom
    raise FileNotFoundError(
        f"Template '{name_or_path}' not found. Use a built-in name "
        f"({', '.join(t.key for t in list_templates())}) or a folder containing report.html.j2."
    )


# ---------------------------------------------------------------- data model

@dataclass
class Instance:
    issue: Issue
    severity: str
    confidence: str
    url: str
    host: str
    ip: str
    path: str
    location: str
    issue_detail: str
    detail_items: list[str]
    remediation_detail: str
    evidence: list[dict]


@dataclass
class Finding:
    id: str
    anchor: str
    name: str
    type_id: str
    severity: str
    confidence: str
    issue_background: str
    remediation_background: str
    references: str
    classifications: str
    instances: list[Instance] = field(default_factory=list)
    omitted_instances: int = 0
    cwes: list[tuple[int, str]] = field(default_factory=list)       # (id, title) from Burp's classifications
    owasp: list[tuple[str, str]] = field(default_factory=list)      # (code, name), e.g. ("A05", "Injection")
    owasp_edition: str = ""                                         # edition of those codes, e.g. "2025"

    @property
    def hosts(self) -> list[str]:
        return sorted({i.host for i in self.instances})

    @property
    def count(self) -> int:
        return len(self.instances) + self.omitted_instances


def _trim(text: str, limit: int, headers_only: bool = False) -> tuple[str, bool]:
    if headers_only:
        m = re.search(r"\r?\n\r?\n", text)
        if m:
            text, truncated = text[: m.start()], True
            return (text[:limit], True) if limit and len(text) > limit else (text, truncated)
    if limit and len(text) > limit:
        return text[:limit], True
    return text, False


def _evidence(issue: Issue, cfg: ReportConfig, redactor: Redactor) -> list[dict]:
    """Evidence for one issue. "request"/"response" are escaped Markup (with <mark> highlights);
    "*_text" and "*_marks" carry the plain text and highlight ranges for non-HTML outputs."""
    if not cfg.fields.get("evidence") or not (cfg.include_request or cfg.include_response):
        return []
    req_patterns = resp_patterns = []
    if cfg.highlight_payloads:
        found = highlight.candidates(issue.issue_detail, issue.detail_items)
        req_patterns = highlight.compile_candidates(found)
        # One- or two-character payloads (e.g. a single quote) would match all over a response.
        resp_patterns = highlight.compile_candidates([c for c in found if len(c) >= 3])
    out = []
    for ev in issue.evidence:
        req, req_cut = (_trim(redactor.message(ev.request), cfg.max_evidence_chars)
                        if cfg.include_request else ("", False))
        resp, resp_cut = (_trim(redactor.message(ev.response), cfg.max_evidence_chars, cfg.response_headers_only)
                          if cfg.include_response else ("", False))
        if req or resp:
            req_marks = highlight.spans(req, req_patterns)
            resp_marks = highlight.spans(resp, resp_patterns)
            out.append({"request": highlight.to_markup(req, req_marks), "request_text": req, "request_marks": req_marks,
                        "request_truncated": req_cut,
                        "response": highlight.to_markup(resp, resp_marks), "response_text": resp,
                        "response_marks": resp_marks,
                        "response_truncated": resp_cut and not cfg.response_headers_only,
                        "response_headers_only": cfg.response_headers_only and resp_cut,
                        "highlighted": bool(req_marks or resp_marks),
                        "method": ev.method, "redirected": ev.redirected})
    return out


def filter_issues(scan: ScanReport, cfg: ReportConfig) -> list[Issue]:
    hosts = set(cfg.include_hosts)
    excluded = set(cfg.exclude_issue_names)
    return [
        i for i in scan.issues
        if i.severity in cfg.severities
        and i.confidence in cfg.confidences
        and (not hosts or i.host in hosts)
        and i.name not in excluded
    ]


def build_findings(issues: list[Issue], cfg: ReportConfig, redactor: Redactor | None = None) -> list[Finding]:
    if redactor is None:
        redactor = Redactor.from_config(cfg.redact_secrets, cfg.redact_custom)
    groups: dict[tuple, list[Issue]] = {}
    for issue in issues:
        key = (issue.type_id, issue.name) if cfg.group_by_type else (issue.serial, id(issue))
        groups.setdefault(key, []).append(issue)

    findings = []
    for members in groups.values():
        members.sort(key=lambda i: (SEVERITY_RANK.get(i.severity, 9), CONFIDENCE_RANK.get(i.confidence, 9), i.url))
        first = members[0]
        limit = cfg.max_instances_per_finding or len(members)
        instances = [
            Instance(
                issue=m, severity=m.severity, confidence=m.confidence, url=redactor.text(m.url), host=m.host,
                ip=m.ip, path=redactor.text(m.path), location=m.location, issue_detail=m.issue_detail,
                detail_items=m.detail_items, remediation_detail=m.remediation_detail,
                evidence=_evidence(m, cfg, redactor),
            )
            for m in members[:limit]
        ]
        findings.append(Finding(
            id="", anchor="", name=first.name, type_id=first.type_id,
            severity=first.severity, confidence=first.confidence,
            issue_background=first.issue_background,
            remediation_background=first.remediation_background,
            references=first.references, classifications=first.classifications,
            instances=instances, omitted_instances=max(0, len(members) - limit),
        ))
        findings[-1].cwes = parse_cwes(first.classifications)
        findings[-1].owasp = categories([c for c, _ in findings[-1].cwes], cfg.owasp_edition)
        findings[-1].owasp_edition = cfg.owasp_edition

    sorters = {
        "severity": lambda f: (SEVERITY_RANK.get(f.severity, 9), CONFIDENCE_RANK.get(f.confidence, 9), f.name.lower()),
        "name": lambda f: f.name.lower(),
        "host": lambda f: (f.instances[0].host if f.instances else "", SEVERITY_RANK.get(f.severity, 9)),
        "count": lambda f: (-f.count, SEVERITY_RANK.get(f.severity, 9)),
    }
    findings.sort(key=sorters.get(cfg.sort_by, sorters["severity"]))
    width = max(2, len(str(len(findings))))
    for n, f in enumerate(findings, 1):
        f.id = f"{cfg.finding_id_prefix}{n:0{width}d}"
        f.anchor = f"finding-{n}"
    return findings


def _host_summary(issues: list[Issue]) -> list[dict]:
    hosts: dict[str, dict] = {}
    for i in issues:
        h = hosts.setdefault(i.host, {"host": i.host, "ip": i.ip, "counts": Counter(), "total": 0})
        h["counts"][i.severity] += 1
        h["total"] += 1
    return sorted(hosts.values(), key=lambda h: tuple(-h["counts"][s] for s in SEVERITY_ORDER) + (h["host"],))


def _owasp_summary(findings: list[Finding], edition: str) -> dict:
    rows = []
    for code, (name, _) in OWASP_EDITIONS[edition].items():
        members = [f for f in findings if any(c == code for c, _ in f.owasp)]
        rows.append({"code": code, "name": name, "findings": members, "counts": Counter(f.severity for f in members)})
    unmapped = [f for f in findings if not f.owasp]
    return {"edition": edition_label(edition), "year": edition, "rows": rows, "unmapped": unmapped,
            "unmapped_counts": Counter(f.severity for f in unmapped),
            "mapped_total": sum(1 for f in findings if f.owasp)}


def _auto_summary(findings: list[Finding], counts: Counter, hosts: list[dict], cfg: ReportConfig) -> str:
    total = len(findings)
    if not total:
        return "No issues matching the selected criteria were identified during the assessment."
    parts = [f"{counts[s]} {s.lower()}" for s in SEVERITY_ORDER if counts[s]]
    who = f" for {cfg.client}" if cfg.client else ""
    text = (f"This report presents the results of an automated web application security assessment{who} "
            f"performed with Burp Suite Professional. A total of {total} unique "
            f"issue{'s' if total != 1 else ''} were identified across {len(hosts)} "
            f"host{'s' if len(hosts) != 1 else ''}, rated as: {', '.join(parts)}.")
    if counts["High"]:
        top = [f.name for f in findings if f.severity == "High"][:3]
        text += (f"\n\nHigh severity issues require prompt attention, including: {'; '.join(top)}. "
                 f"These should be remediated as a priority and re-tested to confirm the fix.")
    elif counts["Medium"]:
        text += ("\n\nNo high severity issues were identified. Medium severity issues should be "
                 "addressed as part of the regular remediation cycle.")
    text += ("\n\nAutomated scanning may produce false positives and cannot identify every class of "
             "vulnerability; results should be validated and complemented by manual testing.")
    return text


_DATA_IMAGE = re.compile(r"^data:image/(png|jpeg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$")


def _logo_uri(path: str, data_uri: str = "") -> str:
    if not path:
        # Only allow inline images; this ends up in an <img src>.
        return data_uri if data_uri and _DATA_IMAGE.match(data_uri) else ""
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Logo not found: {p}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


# ---------------------------------------------------------------- jinja

def _paragraphs(text: str) -> Markup:
    if not text:
        return Markup("")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return Markup("".join(f"<p>{escape(p).replace(chr(10), Markup('<br>'))}</p>" for p in paras))


def _css_string(value: str) -> Markup:
    """Quote a value for use as a CSS string literal inside a <style> element."""
    out = []
    for ch in value or "":
        if ch.isalnum() or ch in " .,:;!?()-_/@&+%":
            out.append(ch)
        else:
            out.append(f"\\{ord(ch):x} ")
    return Markup('"' + "".join(out) + '"')


_CSS_COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,30}|(rgb|rgba|hsl|hsla)\([0-9.,%\s]+\))$")
_CSS_FONT = re.compile(r"^[\w\s,\-'\"]{1,200}$")


def valid_color(value: str) -> bool:
    return bool(_CSS_COLOR.match(value.strip()))


def valid_font(value: str) -> bool:
    return bool(_CSS_FONT.match(value.strip()))


@lru_cache(maxsize=None)
def _font_face(family: str) -> str:
    filename, weights = BUNDLED_FONTS[family]
    data = base64.b64encode((FONTS_DIR / filename).read_bytes()).decode("ascii")
    return (f'@font-face {{ font-family: "{family}"; font-style: normal; font-weight: {weights}; '
            f'font-display: block; src: url(data:font/woff2;base64,{data}) format("woff2"); }}')


def _font_faces(template_css: str, custom_stack: str) -> Markup:
    """@font-face rules for the bundled fonts referenced (quoted) by the template or named in the custom font stack."""
    custom = {name.strip().strip("'\"").lower() for name in (custom_stack or "").split(",")}
    used = [f for f in BUNDLED_FONTS
            if (f'"{f}"' in template_css or f"'{f}'" in template_css or f.lower() in custom)
            and (FONTS_DIR / BUNDLED_FONTS[f][0]).is_file()]
    return Markup("\n".join(_font_face(f) for f in used))


def _template_css(template_dir: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in (template_dir / "report.html.j2", COMMON_DIR / "base.css") if p.is_file())


def _make_env(template_dir: Path) -> Environment:
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(str(template_dir)), FileSystemLoader(str(COMMON_DIR))]),
        autoescape=select_autoescape(["html", "j2"], default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["burp_html"] = lambda s: Markup(sanitize_html(s or ""))
    env.filters["paragraphs"] = _paragraphs
    env.filters["css_string"] = _css_string
    env.filters["sev_class"] = lambda s: "sev-" + (s or "information").lower().replace(" ", "-")
    return env


def build_context(scan: ScanReport, cfg: ReportConfig, output_format: str = "html") -> dict:
    """Everything a report needs (shared by the HTML/PDF templates and the Word exporter)."""
    issues = filter_issues(scan, cfg)
    redactor = Redactor.from_config(cfg.redact_secrets, cfg.redact_custom)
    findings = build_findings(issues, cfg, redactor)
    counts = Counter(f.severity for f in findings)
    instance_counts = Counter(i.severity for i in issues)
    hosts = _host_summary(issues)

    report_date = cfg.report_date or date.today().strftime("%d %B %Y")
    severities = [s for s in SEVERITY_ORDER if s in cfg.severities]
    ctx = {
        "cfg": cfg,
        "format": output_format,
        "is_pdf": output_format == "pdf",
        "interactive": output_format == "html" and cfg.interactive_html,
        "sections": cfg.sections,
        "fields": cfg.fields,
        "meta": {
            "title": cfg.title, "subtitle": cfg.subtitle, "client": cfg.client,
            "prepared_by": cfg.prepared_by, "company": cfg.company, "date": report_date,
            "version": cfg.version, "classification": cfg.classification,
            "footer": cfg.footer_text, "logo": _logo_uri(cfg.logo_path, cfg.logo_data),
        },
        "executive_summary": cfg.executive_summary or _auto_summary(findings, counts, hosts, cfg),
        "scope": cfg.scope,
        "findings": findings,
        "hosts": hosts,
        "severities": severities,
        "counts": counts,
        "instance_counts": instance_counts,
        "total_findings": len(findings),
        "total_instances": len(issues),
        "max_count": max([counts[s] for s in severities] + [1]),
        "scan": {
            "source": scan.source.name, "burp_version": scan.burp_version,
            "export_time": scan.export_time, "total_issues": len(scan.issues),
            "filtered_out": len(scan.issues) - len(issues),
        },
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "owasp": _owasp_summary(findings, cfg.owasp_edition),
        "redaction": {"enabled": cfg.redact_secrets, "custom": len(redactor.custom), "count": redactor.count},
        "theme": {
            "accent": Markup(cfg.accent_color.strip()) if cfg.accent_color and valid_color(cfg.accent_color) else "",
            "font": Markup(cfg.font_family.strip()) if cfg.font_family and valid_font(cfg.font_family) else "",
        },
    }
    return ctx


def render_html(scan: ScanReport, cfg: ReportConfig, output_format: str = "html") -> str:
    template_dir = resolve_template(cfg.template)
    ctx = build_context(scan, cfg, output_format)
    template_css = _template_css(template_dir)
    ctx["theme"]["font_faces"] = _font_faces(template_css, ctx["theme"]["font"])
    # @page margin boxes (page numbers, classification) don't inherit CSS variables, so pass the font stack literally.
    m = re.search(r"--font:\s*([^;]+);", template_css)
    ctx["theme"]["page_font"] = Markup(m.group(1).strip()) if m and valid_font(m.group(1)) else "sans-serif"
    return _make_env(template_dir).get_template("report.html.j2").render(**ctx)

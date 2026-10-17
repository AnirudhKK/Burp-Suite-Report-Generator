"""Turn a parsed scan + ReportConfig into report HTML using a Jinja2 template."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .config import ReportConfig
from .parser import CONFIDENCE_RANK, SEVERITIES, SEVERITY_RANK, Issue, ScanReport
from .sanitize import sanitize_html

TEMPLATES_DIR = Path(__file__).parent / "templates"
COMMON_DIR = TEMPLATES_DIR / "_common"
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


def _evidence(issue: Issue, cfg: ReportConfig) -> list[dict]:
    if not cfg.fields.get("evidence") or not (cfg.include_request or cfg.include_response):
        return []
    out = []
    for ev in issue.evidence:
        req, req_cut = _trim(ev.request, cfg.max_evidence_chars) if cfg.include_request else ("", False)
        resp, resp_cut = (_trim(ev.response, cfg.max_evidence_chars, cfg.response_headers_only)
                          if cfg.include_response else ("", False))
        if req or resp:
            out.append({"request": req, "request_truncated": req_cut,
                        "response": resp, "response_truncated": resp_cut and not cfg.response_headers_only,
                        "response_headers_only": cfg.response_headers_only and resp_cut,
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


def build_findings(issues: list[Issue], cfg: ReportConfig) -> list[Finding]:
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
                issue=m, severity=m.severity, confidence=m.confidence, url=m.url, host=m.host, ip=m.ip,
                path=m.path, location=m.location, issue_detail=m.issue_detail, detail_items=m.detail_items,
                remediation_detail=m.remediation_detail, evidence=_evidence(m, cfg),
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


def render_html(scan: ScanReport, cfg: ReportConfig, output_format: str = "html") -> str:
    template_dir = resolve_template(cfg.template)
    issues = filter_issues(scan, cfg)
    findings = build_findings(issues, cfg)
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
        "theme": {
            "accent": Markup(cfg.accent_color.strip()) if cfg.accent_color and valid_color(cfg.accent_color) else "",
            "font": Markup(cfg.font_family.strip()) if cfg.font_family and valid_font(cfg.font_family) else "",
        },
    }
    return _make_env(template_dir).get_template("report.html.j2").render(**ctx)

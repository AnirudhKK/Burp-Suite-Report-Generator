"""Report configuration: everything the user can customise, saveable as a JSON profile."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .owasp import DEFAULT_EDITION, EDITIONS

SECTIONS = {
    "cover": "Cover page",
    "toc": "Table of contents",
    "executive_summary": "Executive summary",
    "scope": "Scope & methodology",
    "risk_chart": "Risk overview chart",
    "findings_table": "Findings summary table",
    "hosts_table": "Affected hosts table",
    "owasp_table": "OWASP Top 10 mapping",
    "findings": "Detailed findings",
    "scan_info": "Scan information appendix",
}

OUTPUT_FORMATS = ("html", "pdf", "docx")

FINDING_FIELDS = {
    "issue_background": "Issue background (description)",
    "issue_detail": "Issue detail (instance-specific)",
    "detail_items": "Issue detail items",
    "remediation_background": "Remediation background",
    "remediation_detail": "Remediation detail",
    "references": "References",
    "classifications": "Vulnerability classifications (CWE/CAPEC)",
    "cwe_owasp": "CWE & OWASP Top 10 category",
    "affected_urls": "Affected URLs list",
    "evidence": "HTTP request/response evidence",
}


@dataclass
class ReportConfig:
    # Output
    output_formats: list[str] = field(default_factory=lambda: ["html"])   # any of OUTPUT_FORMATS
    output_path: str = ""          # without extension; extension is added per format
    template: str = "corporate"    # built-in name or path to a template folder
    accent_color: str = ""         # overrides the template's accent colour if set
    font_family: str = ""          # overrides the template's font stack if set
    interactive_html: bool = True  # search / severity filter controls in HTML output
    page_break_per_finding: bool = False

    # Report details
    title: str = "Web Application Security Assessment"
    subtitle: str = ""
    client: str = ""
    prepared_by: str = ""
    company: str = ""
    report_date: str = ""          # blank = today
    version: str = "1.0"
    classification: str = "CONFIDENTIAL"
    logo_path: str = ""
    logo_data: str = ""            # data: URI (used by the web UI when a logo is uploaded)
    finding_id_prefix: str = "F-"

    # Free text (plain text; blank lines separate paragraphs)
    executive_summary: str = ""    # blank = auto-generated
    scope: str = ""
    footer_text: str = ""

    # Sections & per-finding fields
    sections: dict[str, bool] = field(default_factory=lambda: {k: True for k in SECTIONS})
    fields: dict[str, bool] = field(default_factory=lambda: {k: True for k in FINDING_FIELDS})
    owasp_edition: str = DEFAULT_EDITION   # OWASP Top 10 edition for the mapping: "2025" or "2021"

    # Filters
    severities: list[str] = field(default_factory=lambda: ["High", "Medium", "Low", "Information"])
    confidences: list[str] = field(default_factory=lambda: ["Certain", "Firm", "Tentative"])
    include_hosts: list[str] = field(default_factory=list)       # empty = all hosts
    exclude_issue_names: list[str] = field(default_factory=list)

    # Grouping / ordering
    group_by_type: bool = True     # merge instances of the same issue type into one finding
    sort_by: str = "severity"      # severity | name | host | count

    # Evidence
    include_request: bool = True
    include_response: bool = True
    response_headers_only: bool = False
    max_evidence_chars: int = 6000
    max_instances_per_finding: int = 25
    highlight_payloads: bool = True   # mark the payload Burp names in the issue detail inside the evidence
    redact_secrets: bool = True       # mask cookies, auth headers, tokens, passwords and keys in evidence
    redact_custom: list[str] = field(default_factory=list)  # extra values to mask; "/regex/" or "/regex/i" for patterns

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ReportConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict) -> "ReportConfig":
        """Build a config from a profile, keeping defaults for unknown or wrongly typed values."""
        if not isinstance(data, dict):
            raise ValueError("A profile must be a JSON object")
        defaults = cls()
        kwargs = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value, default = data[f.name], getattr(defaults, f.name)
            if isinstance(default, bool):
                ok = isinstance(value, bool)
            elif isinstance(default, int):
                ok = isinstance(value, int) and not isinstance(value, bool)
                value = max(0, value) if ok else value
            elif isinstance(default, str):
                ok = isinstance(value, str)
            elif isinstance(default, list):
                ok = isinstance(value, list) and all(isinstance(x, str) for x in value)
            else:
                ok = isinstance(value, dict)
            if ok:
                kwargs[f.name] = value
        cfg = cls(**kwargs)
        # Fill in any section/field keys added since the profile was saved.
        cfg.sections = {k: bool(cfg.sections.get(k, True)) for k in SECTIONS}
        cfg.fields = {k: bool(cfg.fields.get(k, True)) for k in FINDING_FIELDS}
        cfg.output_formats = [f for f in OUTPUT_FORMATS if f in cfg.output_formats] or ["html"]
        if cfg.sort_by not in ("severity", "name", "host", "count"):
            cfg.sort_by = "severity"
        if cfg.owasp_edition not in EDITIONS:
            cfg.owasp_edition = DEFAULT_EDITION
        return cfg

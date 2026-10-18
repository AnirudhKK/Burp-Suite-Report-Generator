"""Interactive (and scriptable) command-line front end."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import webbrowser
from collections import Counter
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markup import escape as rx
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from . import __version__
from .config import FINDING_FIELDS, OUTPUT_FORMATS, SECTIONS, ReportConfig
from .docx_export import DOCX_AVAILABLE, DOCX_MISSING, render_docx
from .owasp import EDITIONS, edition_label
from .parser import CONFIDENCES, SEVERITIES, ScanReport, parse_burp_xml
from .pdf import available_engine, html_to_pdf
from .redact import compile_custom
from .render import (COMMON_DIR, build_findings, filter_issues, list_templates, render_html,
                     resolve_template, valid_color, valid_font)

console = Console(highlight=False)

SEV_STYLE = {"High": "bold red", "Medium": "bold dark_orange", "Low": "bold yellow",
             "Information": "bold blue", "False positive": "dim"}

ACCENT_PRESETS = [
    ("Template default", ""), ("Navy", "#1f3a5f"), ("Royal purple", "#5b3cc4"), ("Teal", "#0f766e"),
    ("Crimson", "#b91c1c"), ("Forest", "#166534"), ("Charcoal", "#222222"),
]
FONT_PRESETS = [
    ("Template default", ""),
    ("Inter (modern sans)", '"Inter", "Segoe UI", system-ui, Arial, sans-serif'),
    ("Source Sans 3 (formal sans)", '"Source Sans 3", "Segoe UI", system-ui, Arial, sans-serif'),
    ("IBM Plex Sans (technical sans)", '"IBM Plex Sans", "Helvetica Neue", Arial, sans-serif'),
    ("Source Serif 4 (formal serif)", '"Source Serif 4", Georgia, "Times New Roman", serif'),
    ("Segoe UI / system", '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif'),
    ("Calibri", "Calibri, Carlito, Arial, sans-serif"),
    ("Georgia (serif)", 'Georgia, "Times New Roman", serif'),
]


# ---------------------------------------------------------------- helpers

def sev(s: str) -> str:
    return f"[{SEV_STYLE.get(s, '')}]{s}[/]"


def parse_selection(text: str, n: int) -> set[int]:
    """'1,3-5' -> {0,2,3,4} (zero-based); ignores out-of-range numbers."""
    picked: set[int] = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            if a.isdigit() and b.isdigit():
                picked.update(range(int(a) - 1, int(b)))
        elif part.isdigit():
            picked.add(int(part) - 1)
    return {i for i in picked if 0 <= i < n}


def toggle_menu(title: str, options: list[tuple[str, str]], selected: set[str], min_one: bool = False) -> set[str]:
    """Checkbox-style multi-select. options = [(key, label)]."""
    selected = set(selected)
    while True:
        t = Table(title=title, box=box.SIMPLE, title_justify="left", show_header=False)
        t.add_column(justify="right", style="cyan")
        t.add_column()
        t.add_column()
        for n, (key, label) in enumerate(options, 1):
            t.add_row(str(n), "[green]\\[x][/]" if key in selected else "[dim]\\[ ][/]", label)
        console.print(t)
        ans = Prompt.ask("Toggle numbers (e.g. [cyan]1,3-5[/]), [cyan]a[/]=all, [cyan]n[/]=none, "
                         "[cyan]Enter[/]=done", default="", show_default=False).strip().lower()
        if not ans:
            if min_one and not selected:
                console.print("[red]Select at least one option.[/]")
                continue
            return selected
        if ans in ("a", "all"):
            selected = {k for k, _ in options}
        elif ans in ("n", "none"):
            selected = set()
        else:
            for i in parse_selection(ans, len(options)):
                selected ^= {options[i][0]}


def choose(title: str, options: list[str], default: int = 1) -> int:
    """Single choice from a numbered list; returns zero-based index."""
    for n, label in enumerate(options, 1):
        console.print(f"  [cyan]{n}[/]. {label}")
    while True:
        i = IntPrompt.ask(title, default=default)
        if 1 <= i <= len(options):
            return i - 1
        console.print(f"[red]Enter a number between 1 and {len(options)}.[/]")


def ask_text(label: str, current: str) -> str:
    val = Prompt.ask(f"{label} [dim](- to clear)[/]", default=current or "", show_default=bool(current))
    return "" if val.strip() == "-" else val.strip()


def ask_multiline(label: str, current: str) -> str:
    console.print(Panel(rx(current) if current else "[dim](empty)[/]", title=f"Current {label}", title_align="left", expand=False))
    console.print(f"Enter new {label}. Finish with a line containing only [cyan].[/]  ·  "
                  "[cyan]@path\\to\\file.txt[/] loads from a file  ·  [cyan]Enter[/] on the first line keeps current  ·  "
                  "[cyan]-[/] clears")
    lines: list[str] = []
    while True:
        try:
            line = input("> " if not lines else "  ")
        except EOFError:
            break
        if not lines:
            s = line.strip()
            if s == "":
                return current
            if s == "-":
                return ""
            if s.startswith("@"):
                p = Path(s[1:].strip().strip('"')).expanduser()
                try:
                    return p.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    console.print(f"[red]Could not read {rx(str(p))}: {rx(str(exc))}[/]")
                    return current
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def ask_path(label: str, must_exist: bool = True, default: str = "") -> Path:
    while True:
        raw = Prompt.ask(label, default=default or None).strip().strip('"').strip("'")
        p = Path(raw).expanduser()
        if not must_exist or p.exists():
            return p
        console.print(f"[red]Not found:[/] {rx(str(p))}")


# ---------------------------------------------------------------- summaries

def scan_summary(scan: ScanReport) -> None:
    counts = Counter(i.severity for i in scan.issues)
    t = Table(box=box.ROUNDED, title=rx(scan.source.name), title_justify="left")
    for s in SEVERITIES:
        if counts[s] or s != "False positive":
            t.add_column(sev(s), justify="center")
    t.add_column("Total", justify="center")
    t.add_row(*[str(counts[s]) for s in SEVERITIES if counts[s] or s != "False positive"], str(len(scan.issues)))
    console.print(t)
    console.print(f"[dim]{len(scan.issue_names)} issue types · {len(scan.hosts)} host(s)"
                  f"{' · Burp ' + rx(scan.burp_version) if scan.burp_version else ''}"
                  f"{' · exported ' + rx(scan.export_time) if scan.export_time else ''}[/]")


def config_overview(cfg: ReportConfig, scan: ScanReport) -> Table:
    issues = filter_issues(scan, cfg)
    findings = build_findings(issues, cfg)
    on_sections = sum(cfg.sections.values())
    on_fields = sum(cfg.fields.values())
    hosts = "all hosts" if not cfg.include_hosts else f"{len(cfg.include_hosts)}/{len(scan.hosts)} hosts"
    ev = "off" if not cfg.fields.get("evidence") else (
        ", ".join(x for x, on in (("requests", cfg.include_request),
                                 ("responses" + (" (headers only)" if cfg.response_headers_only else ""),
                                  cfg.include_response)) if on) or "off")
    rows = [
        ("1", "Output", f"{' + '.join(f.upper() for f in cfg.output_formats)} → {rx(cfg.output_path)}.*"),
        ("2", "Template & styling", rx(cfg.template)
         + (f" · accent {rx(cfg.accent_color)}" if cfg.accent_color else "")
         + (" · custom font" if cfg.font_family else "")
         + (" · page break per finding" if cfg.page_break_per_finding else "")),
        ("3", "Report details", rx(cfg.title) + (f" · {rx(cfg.client)}" if cfg.client else "")
         + (" · logo" if cfg.logo_path else "")),
        ("4", "Sections", f"{on_sections}/{len(SECTIONS)} enabled · {edition_label(cfg.owasp_edition)}"),
        ("5", "Finding fields", f"{on_fields}/{len(FINDING_FIELDS)} enabled"),
        ("6", "Filters", f"{', '.join(cfg.severities) or 'no severities!'} · {', '.join(cfg.confidences)} · {hosts}"
         + (f" · {len(cfg.exclude_issue_names)} issue type(s) excluded" if cfg.exclude_issue_names else "")),
        ("7", "Grouping & sorting", ("grouped by issue type" if cfg.group_by_type else "one finding per instance")
         + f" · sort by {cfg.sort_by} · ID prefix '{rx(cfg.finding_id_prefix)}'"),
        ("8", "Evidence", ev + (" · secrets redacted" if cfg.redact_secrets else " · [yellow]no redaction[/]")
         + (f" · {len(cfg.redact_custom)} custom redaction(s)" if cfg.redact_custom else "")
         + (" · payloads highlighted" if cfg.highlight_payloads else "")
         + (f" · max {cfg.max_evidence_chars} chars" if cfg.max_evidence_chars else "")
         + (f" · max {cfg.max_instances_per_finding} instances/finding" if cfg.max_instances_per_finding else "")),
        ("9", "Summary & text", ("custom executive summary" if cfg.executive_summary else "auto executive summary")
         + (" · scope text" if cfg.scope else "") + (" · footer text" if cfg.footer_text else "")),
    ]
    t = Table(box=box.ROUNDED, show_header=False, title="Report settings", title_justify="left")
    t.add_column(style="cyan", justify="right")
    t.add_column(style="bold")
    t.add_column(overflow="fold")
    for r in rows:
        t.add_row(*r)
    t.caption = f"Result: {len(findings)} findings from {len(issues)} of {len(scan.issues)} issues"
    return t


def preview_findings(cfg: ReportConfig, scan: ScanReport) -> None:
    findings = build_findings(filter_issues(scan, cfg), cfg)
    t = Table(box=box.SIMPLE_HEAD, title="Findings that will be in the report", title_justify="left")
    t.add_column("ID", style="cyan")
    t.add_column("Finding")
    t.add_column("Severity")
    t.add_column("Confidence")
    t.add_column("Inst.", justify="right")
    for f in findings:
        t.add_row(rx(f.id), rx(f.name), sev(f.severity), f.confidence, str(f.count))
    console.print(t if findings else "[yellow]No findings match the current filters.[/]")


# ---------------------------------------------------------------- editors

def edit_output(cfg: ReportConfig) -> None:
    engine = available_engine()
    pdf_note = f"[green]PDF engine: {engine}[/]" if engine else "[red]no PDF engine found (see README)[/]"
    docx_note = "" if DOCX_AVAILABLE else f"  [red]{rx(DOCX_MISSING)}[/]"
    console.print(f"\n[bold]Output format[/]  {pdf_note}{docx_note}")
    labels = {"html": "HTML (interactive, single file)", "pdf": "PDF", "docx": "Word (.docx, editable)"}
    picked = toggle_menu("Formats to generate", [(f, labels[f]) for f in OUTPUT_FORMATS], set(cfg.output_formats), True)
    cfg.output_formats = [f for f in OUTPUT_FORMATS if f in picked]
    if "html" in cfg.output_formats:
        cfg.interactive_html = Confirm.ask("Add search & severity filter controls to the HTML report?",
                                           default=cfg.interactive_html)
    out = Prompt.ask("Output file (extension added automatically)", default=cfg.output_path).strip().strip('"')
    cfg.output_path = str(Path(out).with_suffix("")) if Path(out).suffix.lower() in (".html", ".pdf", ".htm", ".docx") else out


def export_template(src_key: str, dest: Path) -> Path:
    src = resolve_template(src_key)
    dest.mkdir(parents=True, exist_ok=True)
    for f in list(src.iterdir()) + list(COMMON_DIR.iterdir()):
        if f.is_file():
            shutil.copy2(f, dest / f.name)
    return dest


def edit_template(cfg: ReportConfig) -> None:
    templates = list_templates()
    console.print("\n[bold]Template[/]")
    labels = [f"[bold]{rx(t.name)}[/] [dim]– {rx(t.description)}[/]" for t in templates]
    labels += ["Custom template folder…", "Export a built-in template to a folder to customise it…"]
    keys = [t.key for t in templates]
    current = keys.index(cfg.template) + 1 if cfg.template in keys else len(templates) + 1
    i = choose("Template", labels, current)
    if i < len(templates):
        cfg.template = keys[i]
    elif i == len(templates):
        while True:
            p = ask_path("Folder containing report.html.j2")
            try:
                resolve_template(str(p))
                cfg.template = str(p.resolve())
                break
            except FileNotFoundError as exc:
                console.print(f"[red]{rx(str(exc))}[/]")
    else:
        base = keys[choose("Which template to start from", [rx(t.name) for t in templates], 1)]
        dest = ask_path("Destination folder", must_exist=False, default=str(Path.cwd() / "my_template"))
        if dest.exists() and any(dest.iterdir()) and not Confirm.ask(f"{rx(str(dest))} is not empty. Overwrite files?", default=False):
            return
        export_template(base, dest)
        console.print(f"[green]Exported to {rx(str(dest))}[/]. Edit report.html.j2 / base.css there, then select it as a custom template.")
        if Confirm.ask("Use this exported template now?", default=True):
            cfg.template = str(dest.resolve())

    console.print("\n[bold]Accent colour[/]")
    labels = [f"{n} [dim]{v}[/]" for n, v in ACCENT_PRESETS] + ["Custom (hex / CSS colour)…"]
    current = next((n for n, (_, v) in enumerate(ACCENT_PRESETS, 1) if v == cfg.accent_color), len(labels))
    i = choose("Accent", labels, current)
    if i < len(ACCENT_PRESETS):
        cfg.accent_color = ACCENT_PRESETS[i][1]
    else:
        while True:
            c = Prompt.ask("Colour (e.g. #0b5394)", default=cfg.accent_color or "#0b5394").strip()
            if valid_color(c):
                cfg.accent_color = c
                break
            console.print("[red]Use a hex colour like #0b5394, a colour name, or rgb(...).[/]")

    console.print("\n[bold]Font[/]")
    labels = [n for n, _ in FONT_PRESETS] + ["Custom font stack…"]
    current = next((n for n, (_, v) in enumerate(FONT_PRESETS, 1) if v == cfg.font_family), len(labels))
    i = choose("Font", labels, current)
    if i < len(FONT_PRESETS):
        cfg.font_family = FONT_PRESETS[i][1]
    else:
        while True:
            f = Prompt.ask("Font stack (e.g. Verdana, sans-serif)", default=cfg.font_family or None).strip()
            if valid_font(f):
                cfg.font_family = f
                break
            console.print("[red]Only letters, digits, spaces, commas, hyphens and quotes are allowed.[/]")

    cfg.page_break_per_finding = Confirm.ask("Start each finding on a new page (PDF/print)?",
                                             default=cfg.page_break_per_finding)


def edit_details(cfg: ReportConfig) -> None:
    console.print("\n[bold]Report details[/] [dim](Enter keeps the value shown)[/]")
    cfg.title = ask_text("Report title", cfg.title) or "Security Assessment Report"
    cfg.subtitle = ask_text("Subtitle", cfg.subtitle)
    cfg.client = ask_text("Client / target organisation", cfg.client)
    cfg.prepared_by = ask_text("Prepared by (assessor)", cfg.prepared_by)
    cfg.company = ask_text("Your company", cfg.company)
    cfg.report_date = ask_text("Report date (blank = today)", cfg.report_date)
    cfg.version = ask_text("Document version", cfg.version)
    cfg.classification = ask_text("Classification label (e.g. CONFIDENTIAL)", cfg.classification)
    while True:
        logo = ask_text("Logo image path (PNG/JPG/SVG)", cfg.logo_path).strip('"')
        if not logo or Path(logo).expanduser().is_file():
            cfg.logo_path = logo
            break
        console.print(f"[red]File not found: {rx(logo)}[/]")


def edit_sections(cfg: ReportConfig) -> None:
    on = toggle_menu("Sections to include", list(SECTIONS.items()), {k for k, v in cfg.sections.items() if v})
    cfg.sections = {k: k in on for k in SECTIONS}
    editions = list(EDITIONS)
    pick = choose("OWASP Top 10 edition for the mapping section and finding categories",
                  [edition_label(e) + (" (latest)" if n == 0 else "") for n, e in enumerate(editions)],
                  editions.index(cfg.owasp_edition) + 1)
    cfg.owasp_edition = editions[pick]


def edit_fields(cfg: ReportConfig) -> None:
    on = toggle_menu("Fields to show for each finding", list(FINDING_FIELDS.items()),
                     {k for k, v in cfg.fields.items() if v})
    cfg.fields = {k: k in on for k in FINDING_FIELDS}


def edit_filters(cfg: ReportConfig, scan: ScanReport) -> None:
    counts = Counter(i.severity for i in scan.issues)
    cfg.severities = sorted(
        toggle_menu("Severities to include", [(s, f"{sev(s)} ({counts[s]})") for s in SEVERITIES], set(cfg.severities), True),
        key=SEVERITIES.index)
    ccounts = Counter(i.confidence for i in scan.issues)
    cfg.confidences = sorted(
        toggle_menu("Confidence levels to include", [(c, f"{c} ({ccounts[c]})") for c in CONFIDENCES], set(cfg.confidences), True),
        key=CONFIDENCES.index)

    if len(scan.hosts) > 1:
        hcounts = Counter(i.host for i in scan.issues)
        current = set(cfg.include_hosts) or set(scan.hosts)
        picked = toggle_menu("Hosts to include", [(h, f"{rx(h)} ({hcounts[h]})") for h in scan.hosts], current, True)
        cfg.include_hosts = [] if picked == set(scan.hosts) else sorted(picked)

    if Confirm.ask("Exclude specific issue types (e.g. known false positives)?", default=bool(cfg.exclude_issue_names)):
        names = scan.issue_names
        first = {}
        for i in scan.issues:
            first.setdefault(i.name, i.severity)
        ncounts = Counter(i.name for i in scan.issues)
        names.sort(key=lambda n: (SEVERITIES.index(first[n]) if first[n] in SEVERITIES else 9, n))
        included = toggle_menu("Issue types to include (untick to exclude)",
                               [(n, f"{rx(n)} [dim]({ncounts[n]})[/] {sev(first[n])}") for n in names],
                               set(names) - set(cfg.exclude_issue_names))
        cfg.exclude_issue_names = sorted(set(names) - included)


def edit_grouping(cfg: ReportConfig) -> None:
    console.print("\n[bold]Grouping & sorting[/]")
    cfg.group_by_type = choose("Grouping", [
        "Group all instances of an issue type into one finding (recommended)",
        "One finding per issue instance"], 1 if cfg.group_by_type else 2) == 0
    sorts = ["severity", "name", "host", "count"]
    cfg.sort_by = sorts[choose("Sort findings by", ["Severity (then confidence)", "Name", "Host", "Number of instances"],
                               sorts.index(cfg.sort_by) + 1 if cfg.sort_by in sorts else 1)]
    cfg.finding_id_prefix = Prompt.ask("Finding ID prefix (e.g. F-, VULN-, WEB-)", default=cfg.finding_id_prefix)


def edit_evidence(cfg: ReportConfig) -> None:
    console.print("\n[bold]HTTP evidence[/]")
    cfg.fields["evidence"] = Confirm.ask("Include request/response evidence?", default=cfg.fields.get("evidence", True))
    if cfg.fields["evidence"]:
        cfg.include_request = Confirm.ask("  Include HTTP requests?", default=cfg.include_request)
        cfg.include_response = Confirm.ask("  Include HTTP responses?", default=cfg.include_response)
        if cfg.include_response:
            cfg.response_headers_only = Confirm.ask("  Response headers only (drop bodies)?", default=cfg.response_headers_only)
        cfg.max_evidence_chars = IntPrompt.ask("  Max characters per request/response (0 = unlimited)",
                                               default=cfg.max_evidence_chars)
        cfg.highlight_payloads = Confirm.ask("  Highlight the payload Burp names in the issue detail?",
                                             default=cfg.highlight_payloads)
        cfg.redact_secrets = Confirm.ask("  Redact secrets (cookies, auth headers, tokens, passwords, keys)?",
                                         default=cfg.redact_secrets)
        console.print("  [dim]Extra values to redact: one per line, literal text or /regex/ (/regex/i ignores case).[/]")
        while True:
            text = ask_multiline("extra values to redact", "\n".join(cfg.redact_custom))
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            try:
                compile_custom(lines)
                cfg.redact_custom = lines
                break
            except ValueError as exc:
                console.print(f"[red]{rx(str(exc))}[/]")
    cfg.max_instances_per_finding = IntPrompt.ask("Max instances listed per finding (0 = unlimited)",
                                                  default=cfg.max_instances_per_finding)


def edit_text(cfg: ReportConfig) -> None:
    console.print("\n[bold]Executive summary[/] [dim](leave empty to auto-generate from the results)[/]")
    cfg.executive_summary = ask_multiline("executive summary", cfg.executive_summary)
    console.print("\n[bold]Scope & methodology[/] [dim](shown only if the section is enabled and text is present)[/]")
    cfg.scope = ask_multiline("scope & methodology", cfg.scope)
    cfg.footer_text = ask_text("Footer text (e.g. disclaimer)", cfg.footer_text)


# ---------------------------------------------------------------- generation

def generate(scan: ScanReport, cfg: ReportConfig) -> list[Path]:
    written = []
    base = Path(cfg.output_path).expanduser()
    base.parent.mkdir(parents=True, exist_ok=True)
    for fmt in cfg.output_formats:
        if fmt == "docx":
            out = base.with_name(base.name + ".docx")
            with console.status("Building Word document…"):
                out.write_bytes(render_docx(scan, cfg))
            written.append(out)
            continue
        html = render_html(scan, cfg, fmt)
        if fmt == "html":
            out = base.with_name(base.name + ".html")
            out.write_text(html, encoding="utf-8")
        else:
            out = base.with_name(base.name + ".pdf")
            with console.status("Rendering PDF…"):
                html_to_pdf(html, out)
        written.append(out)
    return written


def open_file(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            webbrowser.open(path.resolve().as_uri())
    except OSError as exc:
        console.print(f"[red]Could not open {rx(str(path))}: {rx(str(exc))}[/]")


def interactive(scan: ScanReport, cfg: ReportConfig, quick_setup: bool) -> None:
    if quick_setup:
        console.print(Panel("Quick setup – answer a few questions, then fine-tune anything from the menu.",
                            style="cyan", expand=False))
        edit_output(cfg)
        console.print("\n[bold]Template[/]")
        templates = list_templates()
        keys = [t.key for t in templates]
        cfg.template = keys[choose("Template", [f"[bold]{rx(t.name)}[/] [dim]– {rx(t.description)}[/]" for t in templates],
                                   keys.index(cfg.template) + 1 if cfg.template in keys else 1)]
        cfg.title = ask_text("\nReport title", cfg.title) or cfg.title
        cfg.client = ask_text("Client / target organisation", cfg.client)
        cfg.prepared_by = ask_text("Prepared by", cfg.prepared_by)

    editors = {
        "1": edit_output, "2": edit_template, "3": edit_details, "4": edit_sections, "5": edit_fields,
        "6": lambda c: edit_filters(c, scan), "7": edit_grouping, "8": edit_evidence, "9": edit_text,
    }
    while True:
        console.print()
        console.print(config_overview(cfg, scan))
        console.print("[cyan]1-9[/] edit · [cyan]p[/] preview findings · [cyan]s[/] save profile · "
                      "[cyan]g[/] generate · [cyan]q[/] quit")
        choice = Prompt.ask("Choice", default="g").strip().lower()
        if choice in editors:
            editors[choice](cfg)
        elif choice == "p":
            preview_findings(cfg, scan)
        elif choice == "s":
            p = ask_path("Save profile as", must_exist=False, default="report_profile.json")
            cfg.save(p)
            console.print(f"[green]Saved {rx(str(p))}[/] – reuse with [cyan]--profile {rx(str(p))}[/]")
        elif choice == "g":
            if not cfg.severities:
                console.print("[red]No severities selected – nothing to report.[/]")
                continue
            try:
                files = generate(scan, cfg)
            except Exception as exc:  # surface template/PDF errors without losing the session
                console.print(f"[bold red]Generation failed:[/] {rx(str(exc))}")
                continue
            for f in files:
                console.print(f"[green]✔ Wrote[/] {rx(str(f.resolve()))}")
            if Confirm.ask("Open the report now?", default=True):
                for f in files:
                    open_file(f)
            if not Confirm.ask("Keep customising (and regenerate)?", default=False):
                if Confirm.ask("Save these settings as a profile for next time?", default=False):
                    p = ask_path("Save profile as", must_exist=False, default="report_profile.json")
                    cfg.save(p)
                    console.print(f"[green]Saved {rx(str(p))}[/]")
                return
        elif choice == "q":
            return


# ---------------------------------------------------------------- entry point

def parse_formats(value: str) -> list[str]:
    value = value.strip().lower()
    if value == "both":
        return ["html", "pdf"]
    if value == "all":
        return list(OUTPUT_FORMATS)
    picked = [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in picked if v not in OUTPUT_FORMATS]
    if bad or not picked:
        raise argparse.ArgumentTypeError(f"unknown format {', '.join(bad) or value!r}: use html, pdf, docx, both or all")
    return [f for f in OUTPUT_FORMATS if f in picked]


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="burp-report",
        description="Convert Burp Suite Professional XML issue exports into customisable HTML / PDF reports.",
    )
    p.add_argument("xml", nargs="?", help="Burp Suite XML export (prompted for if omitted)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("-p", "--profile", help="load settings from a saved JSON profile")
    p.add_argument("-o", "--output", help="output path without extension")
    p.add_argument("-f", "--format", type=parse_formats, metavar="FORMATS",
                   help="html, pdf, docx, both (html+pdf), all, or a comma list such as html,docx")
    p.add_argument("-t", "--template", help="built-in template name or custom template folder")
    p.add_argument("--title", help="report title")
    p.add_argument("--client", help="client name")
    p.add_argument("--min-severity", choices=["High", "Medium", "Low", "Information"],
                   help="include this severity and above")
    p.add_argument("--owasp", choices=list(EDITIONS), metavar="EDITION",
                   help=f"OWASP Top 10 edition for the mapping: {' or '.join(EDITIONS)} (default {next(iter(EDITIONS))})")
    p.add_argument("-y", "--batch", action="store_true", help="no prompts: generate straight away")
    p.add_argument("--cli", action="store_true", help="use the terminal wizard instead of the web UI")
    p.add_argument("--port", type=int, default=0, help="web UI port (default: random free port)")
    p.add_argument("--no-browser", action="store_true", help="start the web UI without opening a browser")
    p.add_argument("--list-templates", action="store_true", help="list built-in templates and exit")
    p.add_argument("--export-template", nargs=2, metavar=("NAME", "DEST"),
                   help="copy a built-in template to DEST for customisation and exit")
    return p


def run_web(args: argparse.Namespace) -> int:
    from .web import serve

    try:
        profile = ReportConfig.load(args.profile) if args.profile else None
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Could not load profile:[/] {rx(str(exc))}")
        return 2
    overrides = {"template": args.template, "title": args.title, "client": args.client, "owasp_edition": args.owasp}
    if any(overrides.values()) or args.min_severity:
        profile = profile or ReportConfig()
        for k, v in overrides.items():
            if v:
                setattr(profile, k, v)
        if args.min_severity:
            profile.severities = SEVERITIES[: SEVERITIES.index(args.min_severity) + 1]
    try:
        serve(args.xml, profile, port=args.port, open_browser=not args.no_browser)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Could not start:[/] {rx(str(exc))}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    # Redirected output on Windows may use a legacy code page; never crash on symbols like "→".
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_arg_parser().parse_args(argv)

    if args.list_templates:
        for t in list_templates():
            console.print(f"[bold cyan]{rx(t.key):<10}[/] {rx(t.description)}")
        return 0
    if args.export_template:
        name, dest = args.export_template[0], Path(args.export_template[1])
        if (dest / "report.html.j2").exists():
            console.print(f"[red]{rx(str(dest))} already contains a template; choose an empty folder.[/]")
            return 2
        try:
            dest = export_template(name, dest)
        except FileNotFoundError as exc:
            console.print(f"[red]{rx(str(exc))}[/]")
            return 2
        console.print(f"[green]Exported to {rx(str(dest))}[/]. Use it with: --template \"{rx(str(dest))}\"")
        return 0

    if not args.batch and not args.cli:
        return run_web(args)

    if not args.batch:
        console.print(Panel.fit("[bold]Burp Suite Report Generator[/]\nXML → HTML / PDF", border_style="cyan"))

    try:
        if args.xml:
            xml_path = Path(args.xml).expanduser()
        elif args.batch:
            console.print("[red]An XML file is required with --batch.[/]")
            return 2
        else:
            xml_path = ask_path("Path to Burp Suite XML export")
        scan = parse_burp_xml(xml_path)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Could not read the report:[/] {rx(str(exc))}")
        return 1

    try:
        cfg = ReportConfig.load(args.profile) if args.profile else ReportConfig()
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Could not load profile:[/] {rx(str(exc))}")
        return 2
    if args.output:
        cfg.output_path = str(Path(args.output).with_suffix("")) if Path(args.output).suffix.lower() in (".html", ".pdf", ".docx") else args.output
    if not cfg.output_path:
        cfg.output_path = str(xml_path.with_name(xml_path.stem + "_report"))
    if args.format:
        cfg.output_formats = args.format
    if args.template:
        cfg.template = args.template
    if args.title:
        cfg.title = args.title
    if args.client:
        cfg.client = args.client
    if args.min_severity:
        cfg.severities = SEVERITIES[: SEVERITIES.index(args.min_severity) + 1]
    if args.owasp:
        cfg.owasp_edition = args.owasp
    try:
        resolve_template(cfg.template)
    except FileNotFoundError as exc:
        console.print(f"[red]{rx(str(exc))}[/]")
        return 2

    if args.batch:
        try:
            for f in generate(scan, cfg):
                console.print(f"Wrote {rx(str(f.resolve()))}")
        except Exception as exc:
            console.print(f"[bold red]Generation failed:[/] {rx(str(exc))}")
            return 1
        return 0

    scan_summary(scan)
    if not scan.issues:
        console.print("[yellow]The export contains no issues; the report will be empty.[/]")
    quick = not args.profile and not Confirm.ask("Skip quick setup and go straight to the full menu?", default=False)
    try:
        interactive(scan, cfg, quick_setup=quick)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/]")
        return 130
    return 0

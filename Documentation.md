# Burp Suite Report Generator: Documentation

The complete guide. For a quick start, see [README.md](README.md).

## Contents

1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Exporting issues from Burp](#3-exporting-issues-from-burp)
4. [Web UI (Burp Report Studio)](#4-web-ui-burp-report-studio)
5. [Terminal wizard](#5-terminal-wizard)
6. [Command-line reference](#6-command-line-reference)
7. [Profiles (saved settings)](#7-profiles-saved-settings)
8. [What goes into a report](#8-what-goes-into-a-report)
9. [Evidence: payload highlighting and redaction](#9-evidence-payload-highlighting-and-redaction)
10. [OWASP Top 10 and CWE](#10-owasp-top-10-and-cwe)
11. [Word export](#11-word-export)
12. [Templates and fonts](#12-templates-and-fonts)
13. [Making your own template](#13-making-your-own-template)
14. [Security notes](#14-security-notes)
15. [Building the Windows exe](#15-building-the-windows-exe)
16. [Tests](#16-tests)
17. [Troubleshooting](#17-troubleshooting)
18. [Project layout](#18-project-layout)

---

## 1. Overview

Burp Suite Report Generator turns a **Burp Suite Professional XML issue export** into a client-ready report in
**HTML**, **PDF** and/or **Word (.docx)**. You choose the template, branding, sections, fields, filters and how
HTTP evidence is shown, and see the result live before exporting.

There are three ways to use it, all with the same options:

| Mode | Start it with | Best for |
|---|---|---|
| Web UI (default) | `python generate_report.py` or double-click the exe | Designing a report with a live preview |
| Terminal wizard | `python generate_report.py scan.xml --cli` | Working over SSH or without a browser |
| Batch | `python generate_report.py scan.xml -y ...` | Scripts and repeat reports from a saved profile |

Everything works offline: the fonts, the CWE → OWASP Top 10 mapping and all web UI assets ship with the tool.
Nothing is uploaded anywhere.

## 2. Installation

### Option A: Python (Windows, macOS, Linux)

Requires **Python 3.10 or newer**.

```powershell
git clone https://github.com/AnirudhKK/Burp-Suite-Report-Generator.git
cd Burp-Suite-Report-Generator
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python generate_report.py --version
```

`requirements.txt` installs:

| Package | Used for |
|---|---|
| Jinja2 | HTML templates |
| rich | the terminal wizard and console output |
| python-docx | Word export (the rest of the tool works without it) |

### Option B: Windows executable (no Python needed)

1. Open the [**Releases** page](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/latest) and download `BurpReportGenerator-v<version>.exe`, plus its
   `.sha256` file if you want to verify it.
2. Optional: check the download. The two hashes must match.
   ```powershell
   (Get-FileHash .\BurpReportGenerator-v1.0.3.exe -Algorithm SHA256).Hash
   Get-Content .\BurpReportGenerator-v1.0.3.exe.sha256
   ```
3. Double-click the exe to open the web UI, or run it from a terminal with the same options as
   `generate_report.py`:
   ```powershell
   .\BurpReportGenerator-v1.0.3.exe scan.xml -y -f all -o reports\acme
   ```

Notes:

- The exe isn't code-signed, so Windows SmartScreen may say **"Windows protected your PC"** the first time. Click
  **More info → Run anyway**. If Microsoft Defender ever flags it, report it at
  <https://www.microsoft.com/wdsi/filesubmission> as "incorrectly detected".
- Startup takes a few seconds, because the exe unpacks itself to a temporary folder each time.
- A console window stays open while the web UI runs. Close it, or press `Ctrl+C`, to stop the tool.

### PDF engine

PDF output is rendered by a headless Chromium browser, so the result matches what you see in the preview.

| Source | Notes |
|---|---|
| Microsoft Edge | Ships with Windows 10/11; used automatically |
| Google Chrome, Chromium, Brave | Found automatically in their standard install locations |
| `BURP_REPORT_BROWSER` environment variable | Full path to any Chromium-based browser executable |
| WeasyPrint | Fallback if no browser is found: `pip install weasyprint` (Python install only) |

HTML and Word export don't need a browser.

### Environment variables

| Variable | Effect |
|---|---|
| `BURP_REPORT_BROWSER` | Browser executable used for PDF output |
| `BURP_REPORT_EXE` | Tests only: run the web UI tests against a built exe |
| `BURP_REPORT_TEST_BROWSER` | Tests only: Playwright browser channel (default `msedge`, e.g. `chrome`) |

## 3. Exporting issues from Burp

1. In Burp Suite Professional, open **Target → Site map** (or **Dashboard → Issue activity**).
2. Select the issues to report. Selecting a host selects all of its issues.
3. Right-click and choose **Report selected issues**.
4. Choose **XML**.
5. Tick **Include requests** and **Include responses** if you want HTTP evidence in the report.
   Base64-encoded messages are fine.
6. Save the file and load it into the tool.

The parser accepts any Burp `<issues>` export. Severity and confidence spellings are normalised (`HIGH`, `info`,
`Informational` and similar), so exports from older Burp versions work too. Binary response bodies such as images,
fonts and PDFs are replaced with a short note.

## 4. Web UI (Burp Report Studio)

```powershell
python generate_report.py                          # opens the studio in your browser
python generate_report.py scan.xml                 # same, with the scan already loaded
python generate_report.py scan.xml -p acme.json    # start from a saved profile
python generate_report.py --port 8080 --no-browser # fixed port; open http://127.0.0.1:8080 yourself
```

To load a scan, click **browse**, drop the XML file onto the window, or click **Try the sample report** to try
the tool with the bundled example.

### Settings (left side)

| Panel | What you can set |
|---|---|
| Template & styling | Template cards with live thumbnails of *your* scan · accent colour (swatches or picker) · font · custom template folder |
| Report details | Title, subtitle, client, prepared by, organisation, date, version, classification label, finding ID prefix, logo upload |
| Sections | Which report sections appear (see [section 8](#8-what-goes-into-a-report)) · OWASP Top 10 edition (2025 or 2021) |
| Finding fields | Which parts of each finding appear |
| Filters | Severity and confidence chips · hosts checklist · searchable issue-type list for dropping false positives |
| Grouping & sorting | One finding per issue type, or one per instance · sort by severity, name, host or count |
| HTTP evidence | Requests and/or responses · headers only · size limit · instances per finding · payload highlighting · redaction and extra values to redact |
| Summary & text | Executive summary (auto-written if left blank), scope & methodology, footer text |

### Preview (right side)

- **Live HTML** re-renders about half a second after each change and keeps your scroll position. Switch between
  desktop, tablet and phone width.
- **PDF** renders the real PDF, so you can check page breaks before exporting.

### Buttons

- **Export HTML**, **Export PDF** and **Export Word** download the finished report.
- **Save profile** downloads your settings as JSON. **Load profile** restores them, and so does dropping the
  profile onto the window. Profiles are interchangeable with the CLI's `-p`.
- **Reset** returns every setting to its default.

Your last settings are also remembered in the browser between sessions.

The tool refuses settings that would produce an empty report, such as unticking every severity or every host, and
shows a message explaining why.

## 5. Terminal wizard

```powershell
python generate_report.py scan.xml --cli
```

A short quick setup (formats, template, title, client, author) leads to the settings menu:

| Key | Setting | What you can customise |
|---|---|---|
| 1 | Output | HTML, PDF and/or Word · output path · search/filter toolbar in the HTML report |
| 2 | Template & styling | Built-in or custom template · accent colour · font · page break per finding · export a template to edit |
| 3 | Report details | Title, subtitle, client, assessor, company, date, version, classification, logo |
| 4 | Sections | Cover, contents, executive summary, scope, risk chart, findings table, hosts table, OWASP mapping, detailed findings, appendix · OWASP Top 10 edition |
| 5 | Finding fields | Description, issue detail, detail items, remediation, references, CWE/CAPEC, CWE & OWASP category, affected URLs, evidence |
| 6 | Filters | Severities, confidence levels, hosts, individual issue types |
| 7 | Grouping & sorting | Group by issue type or list each instance · sort order · finding ID prefix |
| 8 | Evidence | Requests/responses · headers only · size limit · payload highlighting · redaction and extra values · max instances per finding |
| 9 | Summary & text | Executive summary, scope & methodology, footer; type text or load it from a file with `@file.txt` |

Other menu keys:

| Key | Action |
|---|---|
| `p` | Preview the list of findings |
| `s` | Save the settings as a JSON profile |
| `g` | Generate the report |
| `q` | Quit |

After generating, you can open the files, keep adjusting settings and generate again.

## 6. Command-line reference

```text
python generate_report.py [xml] [options]
BurpReportGenerator-v<version>.exe [xml] [options]
```

| Option | Description |
|---|---|
| `xml` | Burp XML export. Optional for the web UI; required with `--batch`. |
| `-y`, `--batch` | No prompts: generate the report and exit. |
| `--cli` | Use the terminal wizard instead of the web UI. |
| `-f`, `--format FORMATS` | `html`, `pdf`, `docx`, `both` (HTML + PDF), `all`, or a comma list such as `html,docx`. Default: `html`. |
| `-o`, `--output PATH` | Output path without extension; each format adds its own. Folders are created as needed. Default: `<xml name>_report` next to the XML. |
| `-t`, `--template NAME` | Built-in template (`corporate`, `modern`, `minimal`) or a custom template folder. |
| `-p`, `--profile FILE` | Load settings from a saved JSON profile. |
| `--title TEXT` | Report title. |
| `--client TEXT` | Client name. |
| `--min-severity LEVEL` | Include this severity and above: `High`, `Medium`, `Low` or `Information`. |
| `--owasp EDITION` | OWASP Top 10 edition for the mapping: `2025` (default) or `2021`. |
| `--port N` | Web UI port. Default: a random free port. |
| `--no-browser` | Start the web UI without opening a browser. |
| `--list-templates` | List the built-in templates and exit. |
| `--export-template NAME DEST` | Copy a built-in template to `DEST` for editing, then exit. |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Show help and exit. |

Command-line options override values from `--profile`.

### Examples

```powershell
# Web UI with a scan preloaded
python generate_report.py scan.xml

# HTML + PDF with the modern template
python generate_report.py scan.xml -y -f both -t modern --client "Acme Ltd" -o reports/acme

# Everything (HTML, PDF, Word) from a saved profile, Low and above only
python generate_report.py scan.xml -y -f all -p acme.json --min-severity Low

# Word only, custom template folder
python generate_report.py scan.xml -y -f docx -t ./my_template -o out/report
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | The XML couldn't be read, generation failed, or the web UI couldn't start |
| 2 | Invalid arguments, an unreadable profile, or an unknown template |
| 130 | Cancelled with `Ctrl+C` in the wizard |

## 7. Profiles (saved settings)

A profile is a JSON file holding every setting. The web UI, the wizard and `-p` all read and write the same
format.

Profiles are forgiving:
- Unknown keys are ignored.
- A value of the wrong type keeps its default, and the rest of the profile still loads.
- Sections and fields added in newer versions are switched on automatically.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `output_formats` | list | `["html"]` | Any of `html`, `pdf`, `docx` |
| `output_path` | string | `""` | Output path without extension |
| `template` | string | `"corporate"` | Built-in name or template folder |
| `accent_color` | string | `""` | Overrides the template's accent, e.g. `"#0f766e"` |
| `font_family` | string | `""` | Overrides the template's font stack, e.g. `"\"Inter\", sans-serif"` |
| `interactive_html` | bool | `true` | Search box and severity filter in HTML reports |
| `page_break_per_finding` | bool | `false` | Start each finding on a new page in PDF |
| `title`, `subtitle`, `client`, `prepared_by`, `company` | string | | Report details |
| `report_date` | string | `""` | Blank = today |
| `version` | string | `"1.0"` | Report version shown on the cover |
| `classification` | string | `"CONFIDENTIAL"` | Label on the cover and in the page footer |
| `logo_path` / `logo_data` | string | `""` | Logo file path, or a `data:image/...` URI (the web UI uses this) |
| `finding_id_prefix` | string | `"F-"` | Finding IDs become F-1, F-2, … |
| `executive_summary`, `scope`, `footer_text` | string | `""` | Free text; blank lines separate paragraphs. A blank summary is auto-written. |
| `sections` | object | all `true` | See [section 8](#8-what-goes-into-a-report) |
| `owasp_edition` | string | `"2025"` | OWASP Top 10 edition: `"2025"` or `"2021"` (see [section 10](#10-owasp-top-10-and-cwe)) |
| `fields` | object | all `true` | See [section 8](#8-what-goes-into-a-report) |
| `severities` | list | High, Medium, Low, Information | Add `"False positive"` to include those |
| `confidences` | list | Certain, Firm, Tentative | |
| `include_hosts` | list | `[]` | Empty = all hosts |
| `exclude_issue_names` | list | `[]` | Issue types to leave out |
| `group_by_type` | bool | `true` | One finding per issue type (instances listed inside) |
| `sort_by` | string | `"severity"` | `severity`, `name`, `host` or `count` |
| `include_request`, `include_response` | bool | `true` | HTTP evidence |
| `response_headers_only` | bool | `false` | Drop response bodies |
| `max_evidence_chars` | int | `6000` | Longer messages are truncated (0 = no limit) |
| `max_instances_per_finding` | int | `25` | Extra instances are counted but not shown (0 = all) |
| `highlight_payloads` | bool | `true` | See [section 9](#9-evidence-payload-highlighting-and-redaction) |
| `redact_secrets` | bool | `true` | See [section 9](#9-evidence-payload-highlighting-and-redaction) |
| `redact_custom` | list | `[]` | Extra values to mask: literal text, `/regex/` or `/regex/i` |

Example:

```json
{
  "template": "modern",
  "client": "Acme Ltd",
  "prepared_by": "Security Team",
  "output_formats": ["html", "pdf"],
  "severities": ["High", "Medium", "Low"],
  "sections": {"hosts_table": false},
  "redact_custom": ["internal.acme.local", "/acme-[0-9]{6}/i"]
}
```

## 8. What goes into a report

### Sections (`sections` keys)

| Key | Section |
|---|---|
| `cover` | Cover page with logo, title, client, author, date, version, classification |
| `toc` | Table of contents with links |
| `executive_summary` | Your summary, or an auto-written one based on the findings |
| `scope` | Scope & methodology text |
| `risk_chart` | Severity tiles and chart |
| `findings_table` | Summary table of all findings (with a CWE column when `cwe_owasp` is on) |
| `hosts_table` | Affected hosts with counts per severity |
| `owasp_table` | OWASP Top 10 mapping (edition set by `owasp_edition`) |
| `findings` | Detailed findings |
| `scan_info` | Appendix: source file, Burp version, export time, filters, redaction count |

### Finding fields (`fields` keys)

| Key | Content |
|---|---|
| `issue_background` | Burp's description of the issue type |
| `issue_detail` | Instance-specific detail (e.g. which parameter, which payload) |
| `detail_items` | Lists Burp attaches, such as disclosed e-mail addresses |
| `remediation_background` | General remediation advice |
| `remediation_detail` | Instance-specific remediation |
| `references` | Reference links |
| `classifications` | Burp's CWE/CAPEC list |
| `cwe_owasp` | CWE IDs and OWASP Top 10 categories |
| `affected_urls` | URLs of every instance |
| `evidence` | HTTP requests and responses |

The interactive HTML report also has a toolbar to search findings, filter by severity, expand or collapse all, and
print.

## 9. Evidence: payload highlighting and redaction

### Payload highlighting (on by default)

Burp names the payload in each issue's detail, for example "The payload `abc<script>alert(1)</script>xyz` was
submitted". The report highlights where that payload appears in the request and response, whether it's raw,
URL-encoded, HTML-encoded or `\u`-escaped.

- **Also highlighted:** distinctive values such as a reflected origin, or disclosed e-mail addresses.
- **Very short payloads:** payloads of one or two characters (e.g. `'`) are only highlighted in the request, so
  the whole response isn't lit up.
- **In Word:** highlights appear as yellow text highlighting.

### Redaction (on by default)

Secrets are replaced with `[REDACTED]` in evidence and in URLs:

- **Cookies:** every value in `Cookie` and `Set-Cookie` headers.
- **Credentials:** `Authorization` and `Proxy-Authorization` values. The scheme (`Bearer`, `Basic`) is kept.
- **Sensitive headers:** headers named like secrets, such as `X-Api-Key` and `X-CSRF-Token`. Informational headers
  such as `WWW-Authenticate` are kept.
- **Sensitive names:** query/body parameters, JSON keys and hidden `<input>` values named like passwords, tokens,
  keys, sessions, CSRF values or signatures.
- **Recognisable tokens:** JWTs, AWS access keys, GitHub and Slack tokens, Google API keys, and PEM private-key
  blocks.

**Extra values to redact** (`redact_custom`) take one entry per line:

| Entry | Masks |
|---|---|
| `internal.acme.local` | That exact text |
| `/acme-[0-9]{6}/` | Matches of the regular expression |
| `/x-internal-.*/i` | Matches, ignoring case |

An invalid regular expression is reported straight away, and nothing is generated until you fix it.

What redaction does and doesn't change:
- The report's appendix states how many values were masked.
- Only the report changes; the Burp file is never modified.
- Issue descriptions written by Burp are not redacted.
- Switching off the built-in rules still applies your extra values.

## 10. OWASP Top 10 and CWE

Burp's export lists the CWEs for each issue type. The report uses them in three places:

- **Each finding:** the CWE IDs and titles, and the OWASP Top 10 categories they fall under, tagged with the
  edition (e.g. `A05:2025 Injection`).
- **Findings summary table:** a CWE column.
- **OWASP Top 10 mapping section:** one row per category (A01–A10) with severity counts and links to the
  matching findings, plus a "Not mapped" row.

### Choosing the edition

**OWASP Top 10:2025** is the default. Choose **2021** instead when a client, contract or compliance document
still refers to the older list. All headings and category tags follow the edition you choose.

| Where | How |
|---|---|
| Web UI | **Sections → OWASP Top 10 edition** |
| Terminal wizard | Menu **4 (Sections)**, then pick the edition |
| Command line | `--owasp 2025` or `--owasp 2021` |
| Profile | `"owasp_edition": "2025"` or `"2021"` |

The two editions side by side:

| Code | 2025 (default) | 2021 |
|---|---|---|
| A01 | Broken Access Control (now includes SSRF) | Broken Access Control |
| A02 | Security Misconfiguration | Cryptographic Failures |
| A03 | Software Supply Chain Failures | Injection |
| A04 | Cryptographic Failures | Insecure Design |
| A05 | Injection | Security Misconfiguration |
| A06 | Insecure Design | Vulnerable and Outdated Components |
| A07 | Authentication Failures | Identification and Authentication Failures |
| A08 | Software or Data Integrity Failures | Software and Data Integrity Failures |
| A09 | Security Logging & Alerting Failures | Security Logging and Monitoring Failures |
| A10 | Mishandling of Exceptional Conditions | Server-Side Request Forgery (SSRF) |

The mapping uses the CWE list OWASP publishes for each category ("List of Mapped CWEs"), taken from OWASP's
source at [github.com/OWASP/Top10](https://github.com/OWASP/Top10) and bundled in `burp_report/owasp.py`, so no
internet connection is needed. A finding can fall into more than one category. A finding whose CWEs aren't in any
category's list appears under "Not mapped".

## 11. Word export

The `.docx` follows the chosen sections, fields, filters, accent colour and redaction settings. It includes:

- a cover page and a table of contents with page numbers (Word offers to update fields when the file opens);
- severity tiles, a risk chart, and the findings, hosts and OWASP tables;
- linked finding IDs and evidence with highlighted payloads;
- "Page X of Y" footers on A4 pages.

Word can't use the web fonts embedded in HTML and PDF reports, so each template uses fonts that come with
Microsoft Office:

| Template | Headings | Body |
|---|---|---|
| corporate | Cambria | Calibri |
| modern | Segoe UI Semibold | Segoe UI |
| minimal | Arial | Arial |

If you set a custom **Font**, Word uses the first font in it. Bundled web fonts are swapped for the closest Office
font: Inter → Segoe UI, Source Sans 3 → Calibri, Source Serif 4 → Cambria, IBM Plex Sans → Arial, and
JetBrains Mono → Consolas.

Custom template folders get the Corporate Word styling with your accent colour, because Word documents
aren't built from the HTML templates.

SVG and WebP logos aren't supported in Word; use PNG or JPG.

## 12. Templates and fonts

| Template | Look | Fonts (HTML/PDF) |
|---|---|---|
| `corporate` | Navy accent, numbered sections, accent cover band | Source Serif 4 headings, Source Sans 3 body |
| `modern` | Gradient cover, finding cards, side navigation in HTML | Inter |
| `minimal` | Compact, monochrome, printer-friendly | IBM Plex Sans |

Request and response evidence uses JetBrains Mono in every template.

### Bundled fonts

The fonts ship in `burp_report/fonts/` as Latin-subset variable fonts under the SIL Open Font License; each
font's licence text sits next to it.

- **Embedding:** a report embeds only the fonts it uses, as data URIs, so HTML and PDF look the same on any
  machine, offline included. This adds roughly 115–160 KB to an HTML report.
- **Other scripts:** characters outside the Latin subset, such as Japanese, fall back to the system fonts
  later in the font stack.
- **Using them elsewhere:** in your own template or in the **Font** option, refer to a bundled font by name:
  `"Inter"`, `"Source Sans 3"`, `"Source Serif 4"`, `"IBM Plex Sans"` or `"JetBrains Mono"`.

## 13. Making your own template

### Step 1: copy a built-in template

```powershell
python generate_report.py --export-template corporate my_template
# or, with the exe:
.\BurpReportGenerator-v1.0.3.exe --export-template corporate my_template
```

This copies the template and the shared files into `my_template/`. It refuses to overwrite a folder that
already has a template.

| File | Purpose |
|---|---|
| `report.html.j2` | Entry point. Extends `base.html.j2` and overrides `{% block styles %}`; the simplest place to restyle. |
| `base.html.j2` | Full page layout, with one block per section. |
| `macros.html.j2` | Building blocks: finding card, evidence, badges, charts. |
| `base.css` | Shared styles and CSS variables. |
| `template.json` | Name and description shown in the template list. |

### Step 2: edit it

**Restyle with CSS variables** in `report.html.j2`:

```jinja
{% extends "base.html.j2" %}
{% block styles %}
:root {
  --accent: #7c2d12;
  --font: "Source Sans 3", "Segoe UI", Arial, sans-serif;
  --heading-font: "Source Serif 4", Georgia, serif;
  --radius: 0;
}
.cover h1 { letter-spacing: -.02em; }
{% endblock %}
```

| CSS variables | Purpose |
|---|---|
| `--accent`, `--accent-ink` | Accent colour and text colour on accent backgrounds |
| `--font`, `--heading-font`, `--mono` | Body, heading and code fonts |
| `--text`, `--muted`, `--bg`, `--surface`, `--border` | Text and surface colours |
| `--code-bg`, `--code-text` | Evidence blocks |
| `--sev-high`, `--sev-medium`, `--sev-low`, `--sev-information`, `--sev-false-positive` | Severity colours |
| `--radius`, `--maxw` | Corner radius and page width |

**Replace or remove a section** by overriding its block in `report.html.j2`. The blocks are:
- `toolbar`, `sidebar`, `cover`, `toc`;
- `executive_summary`, `scope`, `overview`, `hosts`, `owasp`, `findings`;
- `appendix`, `footer`, `styles`, `scripts`.

```jinja
{% block scope %}
<section id="scope">
  <h2>Rules of engagement</h2>
  {{ scope }}
</section>
{% endblock %}
```

**Template variables.** Templates are [Jinja2](https://jinja.palletsprojects.com/). The main variables are:

| Variable | Content |
|---|---|
| `meta` | `title`, `subtitle`, `client`, `prepared_by`, `company`, `date`, `version`, `classification`, `footer`, `logo` |
| `findings` | List of findings (below) |
| `severities`, `counts`, `instance_counts` | Severities in use; finding and instance counts per severity |
| `total_findings`, `total_instances`, `max_count` | Totals and the largest severity count (for charts) |
| `hosts` | Per-host summary rows |
| `owasp` | `edition` (e.g. "OWASP Top 10:2025"), `year`, `rows` (`code`, `name`, `findings`, `counts`), `unmapped`, `mapped_total` |
| `sections`, `fields` | The on/off switches from [section 8](#8-what-goes-into-a-report) |
| `executive_summary`, `scope` | Ready-to-insert HTML paragraphs |
| `scan` | `source`, `burp_version`, `export_time`, `total_issues`, `filtered_out` |
| `redaction` | `enabled`, `custom`, `count` |
| `is_pdf`, `interactive`, `generated_at`, `theme`, `cfg` | Output mode, toolbar flag, timestamp, styling, all settings |

Each finding has these fields:
- `id`, `anchor`, `name`, `severity`, `confidence`;
- `issue_background`, `remediation_background`, `references`, `classifications`;
- `cwes`, a list of (id, title);
- `owasp`, a list of (code, name), and `owasp_edition` (e.g. "2025");
- `hosts`, `count`, `omitted_instances`;
- `instances`, each with `url`, `host`, `path`, `issue_detail`, `detail_items`, `remediation_detail` and
  `evidence`.

Burp's HTML fields are already sanitized. Anything else you output is escaped automatically.

### Step 3: use it

```powershell
python generate_report.py scan.xml -t my_template
```

In the web UI, enter the folder under **Template & styling → Custom template folder**. In the wizard, use
**2 → Custom template folder**. Errors in a template are shown in the preview or the console, and nothing is
written.

## 14. Security notes

- **Untrusted Burp content.** Burp's issue text can contain content reflected from the scanned target. That
  HTML goes through an allow-list sanitizer, which removes scripts, event handlers, images, frames and
  `javascript:` links. External links open in a new tab with `rel="noopener noreferrer"`.
- **Evidence and your own text.** Request and response evidence is always shown as escaped text. Your own
  text fields are escaped too, and colour and font values are validated before they reach CSS.
- **XML.** The parser doesn't resolve external entities (XXE), and files that aren't Burp exports are rejected.
- **Web UI server:**
  - It listens only on `127.0.0.1`.
  - Every API call needs a random token created for that run.
  - Requests with a non-localhost `Host` header are rejected, which blocks DNS rebinding.
  - The app and previews run under a strict Content Security Policy.
  - Other websites open in your browser can't reach the tool.
- **Your data stays on your machine.** Nothing is sent over the network. The only exception is PDF
  rendering, which uses a local browser in headless mode.
- **Before sharing a report**, keep redaction on (the default) and check the appendix's redaction count. Add
  client-specific values, such as internal hostnames and account IDs, under **Extra values to redact**.

## 15. Building the Windows exe

### Locally

```powershell
pip install -r requirements-dev.txt
pyinstaller packaging/BurpReportGenerator.spec --noconfirm --clean
# result: dist/BurpReportGenerator-v<version>.exe
```

The exe's name and its Windows version details come from `__version__` in `burp_report/__init__.py`.
`packaging/` holds the PyInstaller spec and the icon. `make_icon.py` redraws the icon; it needs Pillow.

### With GitHub Actions

`.github/workflows/build-exe.yml` runs three jobs:

1. **test**: unit tests and web UI tests on a Windows runner.
2. **build**:
   1. builds the exe;
   2. checks `--version` and `--list-templates`;
   3. exports the sample scan to HTML, PDF and Word;
   4. runs the web UI tests again, with the exe serving the app;
   5. writes a SHA-256 checksum.
3. **release**: for version tags only, publishes a GitHub Release with the exe, its checksum, and notes
   covering SmartScreen and how to verify the download.

When each job runs:

| Trigger | test | build | release |
|---|---|---|---|
| Push to `main`/`master` or a pull request (changes other than `.md` files) | ✔ | ✔ (exe kept 14 days under **Artifacts**) | |
| Push of a `v*` tag | ✔ | ✔ (kept 90 days) | ✔ |
| **Actions → Build Windows exe → Run workflow** | ✔ | ✔ | |

Pushes that change only Markdown files, such as this documentation, don't start the workflow.

### Releasing a new version

```powershell
# 1. bump the version in burp_report/__init__.py, e.g. __version__ = "1.1.0"
git add .
git commit -m "Release 1.1.0"
git push
# 2. tag that commit and push the tag
git tag v1.1.0
git push origin v1.1.0
```

The tag must match `__version__`, or the build stops before anything is published. Tags can't be reused, so
always bump the version.

### Dependency updates

Every Monday, Dependabot (`.github/dependabot.yml`) opens two grouped pull requests:
- one for the GitHub Actions versions;
- one for the Python packages in `requirements.txt` and `requirements-dev.txt`.

The workflow tests and builds each one, so merge it once the checks pass.

## 16. Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest                      # everything (about 2 minutes)
python -m pytest -m "not e2e"         # unit tests only (seconds)
python -m pytest tests/e2e            # web UI tests only
python -m pytest -k redact -v         # tests whose name matches "redact"
$env:BURP_REPORT_EXE = "dist\BurpReportGenerator-v1.0.3.exe"; python -m pytest tests/e2e   # test a built exe
```

| Suite | Location | Covers |
|---|---|---|
| Unit | `tests/test_*.py` | Parser (aliases, binary bodies, XXE), sanitizer, redaction, payload highlighting, OWASP mapping, profiles, HTML and Word rendering for every template, command line |
| Web UI | `tests/e2e/` | The studio in Microsoft Edge via Playwright: previews and links, every settings panel, exports in all formats, profiles, uploads and drag-and-drop, malformed input, API security checks, phone layout, a 1,500-issue performance check |

- **Browser:** the web UI tests use the installed Microsoft Edge, so no browser download is needed. Set
  `BURP_REPORT_TEST_BROWSER=chrome` to use Chrome.
- **Order:** the tests run in sequence and share one page, like a person using the app.
- **Failures:** each failure saves a screenshot to `test-results/`, and in CI it's attached to the workflow run.
- **Generated test files:** edge-case inputs are created on the fly by `tests/fixtures.py`:
  - `nasty.xml`, with Unicode, script in names, binary and huge bodies, and a missing host;
  - `large.xml`, with 1,500 issues;
  - a logo image.

## 17. Troubleshooting

| Problem | Fix |
|---|---|
| "No PDF engine found" | Install Edge or Chrome, set `BURP_REPORT_BROWSER` to a Chromium browser executable, or `pip install weasyprint`. |
| Word export unavailable | `pip install python-docx` (included in `requirements.txt` and in the exe). |
| "Expected a Burp `<issues>` export" | The file isn't a Burp issue export. Export again with **Report selected issues → XML**. |
| No evidence in the report | Tick *Include requests/responses* when exporting from Burp, and check **HTTP evidence** settings. |
| SmartScreen "Windows protected your PC" | The exe is unsigned: **More info → Run anyway**. |
| Exe slow to start | Normal; it unpacks to a temporary folder first (a few seconds). |
| Web UI didn't open a browser | Open the URL printed in the console, or use `--port 8080` and go to `http://127.0.0.1:8080`. |
| Word asks to "update fields" on opening | Click **Yes** to fill in the contents page numbers. |
| Japanese/Cyrillic text in a different font | The bundled fonts are Latin-only; other scripts use system fonts. |
| Custom template not found | The folder must contain `report.html.j2`; use `--export-template` to start one. |

## 18. Project layout

```text
generate_report.py          launcher (python generate_report.py ...)
burp_report/
  __init__.py               version number
  __main__.py               python -m burp_report
  parser.py                 Burp XML → Issue objects (safe XML parsing, normalisation)
  sanitize.py               allow-list HTML sanitizer for Burp's issue text
  config.py                 ReportConfig: every option; saved as JSON profiles
  render.py                 filtering, grouping, context building, Jinja2 rendering, font embedding
  redact.py                 secret redaction for evidence
  highlight.py              payload highlighting in evidence
  owasp.py                  CWE → OWASP Top 10 mapping (2025 and 2021 editions)
  docx_export.py            Word (.docx) export
  pdf.py                    HTML → PDF (Edge/Chrome headless, WeasyPrint fallback)
  cli.py                    command-line options and terminal wizard
  web.py                    local web UI server (standard library only)
  webui/index.html          web UI (single file, works offline)
  fonts/                    bundled OFL fonts (+ licences)
  templates/
    _common/                base.html.j2, macros.html.j2, base.css (shared)
    corporate/ modern/ minimal/   report.html.j2 + template.json each
samples/
  sample_burp_export.xml    example export used by "Try the sample report" and the tests
tests/
  test_*.py                 unit tests
  fixtures.py               generated edge-case inputs
  e2e/                      web UI tests (Playwright + Edge)
packaging/
  BurpReportGenerator.spec  PyInstaller build definition
  icon.ico, make_icon.py    app icon
.github/
  workflows/build-exe.yml   test → build → release workflow
  dependabot.yml            weekly dependency update PRs
requirements.txt            runtime dependencies
requirements-dev.txt        test and build dependencies (pinned)
pytest.ini                  test settings
README.md                   quick start
Documentation.md            this guide
```

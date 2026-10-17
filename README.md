# Burp Suite Report Generator

Turns a **Burp Suite Professional XML issue export** into a polished **HTML** and/or **PDF** report,
through an interactive menu where you choose the template, branding, sections, fields, filters and evidence.

## Setup

```powershell
pip install -r requirements.txt
```

Python 3.10+ is required. PDF output uses a headless Chromium browser; **Microsoft Edge already ships with
Windows**, and Chrome, Chromium or Brave also work. If none of these is installed, set `BURP_REPORT_BROWSER`
to a Chromium browser executable, or `pip install weasyprint` as a fallback.

## Exporting from Burp

In Burp: **Target → Site map** (or **Dashboard → Issue activity**), select the issues, right-click and choose
**Report selected issues** → **XML**. Include the requests and responses (base64-encoded is fine) if you want
HTTP evidence in the report.

## Web UI (default)

```powershell
python generate_report.py                         # opens Burp Report Studio in your browser
python generate_report.py scan.xml                # same, with the scan preloaded
python generate_report.py scan.xml -p myco.json   # start from a saved profile
```

This starts a local server on `127.0.0.1` and opens your browser. The window has two parts:

- **Left: settings.** These are grouped into collapsible panels:
  - **Template & styling**: template cards with live thumbnails rendered from your scan, accent colour swatches or a custom colour picker, font, and a custom template folder.
  - **Report details**: title, client, assessor, date, classification, and an uploaded logo.
  - **Sections** and **Finding fields**: checkboxes.
  - **Filters**: severity and confidence chips, a hosts checklist, and a searchable issue-type checklist for dropping false positives.
  - **Grouping & sorting**, **HTTP evidence**, **Summary & text**.
- **Right: live preview.** The report re-renders a moment after each change and keeps your scroll position.
  - **Live HTML** shows the interactive HTML report at desktop, tablet or phone width.
  - **PDF** renders the actual PDF, so you can check page breaks before exporting.

**Export HTML** and **Export PDF** download the finished report. **Save profile** and **Load profile** use the same JSON
format as the CLI. You can also drag and drop a profile, or a new XML file, onto the window. Your last settings are
remembered in the browser.

Options: `--port 8080` uses a fixed port, and `--no-browser` stops the browser from opening. Press `Ctrl+C` in the terminal to stop the server.

The server only listens on localhost. Every API call needs a random per-run token, and requests with a
non-localhost `Host` header are rejected, so other websites open in your browser can't use it.

## Terminal wizard

```powershell
python generate_report.py scan.xml --cli
```

A short quick setup (format, template, title, client) leads to the settings menu:

| Key | Setting | What you can customise |
|---|---|---|
| 1 | Output | HTML, PDF or both · output path · search/filter toolbar in the HTML report |
| 2 | Template & styling | built-in or custom template · accent colour · font · page break per finding · export a template to edit |
| 3 | Report details | title, subtitle, client, assessor, company, date, version, classification label, logo |
| 4 | Sections | cover, contents, executive summary, scope, risk chart, findings table, hosts table, detailed findings, appendix |
| 5 | Finding fields | description, issue detail, detail items, remediation, references, CWE/CAPEC, affected URLs, evidence |
| 6 | Filters | severities, confidence levels, hosts, individual issue types (e.g. to drop false positives) |
| 7 | Grouping & sorting | group instances by issue type or list each one · sort order · finding ID prefix |
| 8 | Evidence | requests and/or responses · headers only · size limit · max instances per finding |
| 9 | Summary & text | executive summary (auto-generated if left blank), scope & methodology, footer; type text or load it with `@file.txt` |

Then **p** previews the findings list, **s** saves the settings as a JSON profile, and **g** generates the report.
After generating you can keep tweaking settings and generate again.

## Non-interactive / scripted use

```powershell
python generate_report.py scan.xml -y -f both -t modern --client "Acme" -o reports/acme
python generate_report.py scan.xml -y -p acme_profile.json --min-severity Low
python generate_report.py --list-templates
```

`-y/--batch` skips all prompts. Command-line flags override values from the profile.

## Templates

Three templates are built in:

- **corporate**: navy accent, serif headings, numbered sections
- **modern**: gradient cover, finding cards, side navigation in HTML
- **minimal**: compact, monochrome and printer-friendly

### Making your own

```powershell
python generate_report.py --export-template corporate my_template
```

This copies the template plus the shared files into `my_template/`:

- `report.html.j2` extends `base.html.j2` and overrides `{% block styles %}`. This is the simplest place to restyle.
- `base.html.j2` is the full page layout, with a block for each section (`cover`, `toc`, `executive_summary`,
  `overview`, `hosts`, `findings`, `appendix`, `footer`, ...). Edit it here or override single blocks in `report.html.j2`.
- `macros.html.j2` holds the building blocks (finding card, evidence, badges, charts).
- `base.css` holds the shared styles and CSS variables (`--accent`, `--font`, `--sev-high`, ...).

Then use it with `-t my_template` or menu option **2 → Custom template folder**. Templates are
[Jinja2](https://jinja.palletsprojects.com/). The available variables are listed at the top of `base.html.j2`.

## Security notes

- Burp's issue text can contain content reflected from the scanned target. That HTML goes through an
  allow-list sanitizer: scripts, event handlers, images and `javascript:` links are removed. Request and response
  evidence is always shown as escaped text.
- The XML parser does not resolve external entities.

## Layout

```
generate_report.py        launcher
burp_report/
  parser.py               Burp XML → Issue objects
  sanitize.py             allow-list HTML sanitizer
  config.py               ReportConfig (all options; saved as JSON profiles)
  render.py               filtering, grouping, Jinja2 rendering
  pdf.py                  HTML → PDF (Edge/Chrome headless, WeasyPrint fallback)
  cli.py                  terminal wizard and command-line options
  web.py                  local web UI server (stdlib only)
  webui/index.html        web UI (single file, works offline)
  templates/              _common/ (shared) + corporate/ modern/ minimal/
samples/sample_burp_export.xml
```

# Burp Suite Report Generator

Turns a **Burp Suite Professional XML issue export** into a polished **HTML**, **PDF** and/or **Word (.docx)**
report, through an interactive menu where you choose the template, branding, sections, fields, filters and evidence.

Everything runs offline: fonts, the CWE → OWASP Top 10 mapping and all assets ship with the tool.

## Setup

```powershell
pip install -r requirements.txt
```

Python 3.10+ is required. Word export uses `python-docx` (in `requirements.txt`). PDF output uses a headless Chromium browser; **Microsoft Edge already ships with
Windows**, and Chrome, Chromium or Brave also work. If none of these is installed, set `BURP_REPORT_BROWSER`
to a Chromium browser executable, or `pip install weasyprint` as a fallback.

### Windows executable (no Python needed)

Download `BurpReportGenerator-v<version>.exe` from the repository's **Releases** page. It is a single
self-contained file. Double-click it to open the web UI, or use it from a terminal exactly like `generate_report.py`,
for example `BurpReportGenerator-v1.0.0.exe scan.xml -y -f all -o reports\acme`. PDF export still uses the Edge or
Chrome installed on the machine. Startup takes a few seconds while it unpacks to a temporary folder. Each release
also has a `.sha256` file for checking the download.

#### How the exe is built (GitHub Actions)

`.github/workflows/build-exe.yml` runs three jobs on Windows runners:

1. **test**: the unit tests and the web UI tests (see [Tests](#tests)).
2. **build**: builds the exe with PyInstaller, then checks it: `--version`, `--list-templates`, an HTML + PDF +
   Word export of the sample scan, and the web UI tests again with the exe serving the app.
3. **release**: on version tags only, publishes the exe and its `.sha256` as a GitHub Release, with notes
   covering the SmartScreen prompt and the checksum.

- **Every push and pull request:** the exe and its checksum are attached to the workflow run under
  **Actions → run → Artifacts** (kept 14 days; 90 for releases).
- **A version tag:** the same build is published as a GitHub Release. To release:
  1. Set `__version__` in `burp_report/__init__.py` (e.g. `"1.1.0"`) and commit it.
  2. Tag and push: `git tag v1.1.0` then `git push origin v1.1.0`. The tag must match `__version__`, or the build stops.
- **By hand:** **Actions → Build Windows exe → Run workflow**.

The exe's file name and its Windows version details are both taken from `__version__`.

To build locally instead (from the project root, with `requirements.txt` and `pyinstaller` installed):

```powershell
pyinstaller packaging/BurpReportGenerator.spec    # writes dist/BurpReportGenerator-v<version>.exe
```

`packaging/` holds the spec and the icon (`make_icon.py` redraws it; it needs Pillow).

#### Unsigned exe and SmartScreen

The exe is not code-signed (a trusted certificate costs money each year, and a self-signed one doesn't stop the
warnings). Windows SmartScreen may therefore show **"Windows protected your PC"** the first time it runs: click
**More info → Run anyway**. Each release's notes say this too.

To confirm a download is the file GitHub Actions built, compare its hash with the release's `.sha256` file:

```powershell
(Get-FileHash .\BurpReportGenerator-v1.0.0.exe -Algorithm SHA256).Hash
```

If Microsoft Defender flags a release, submit the exe at
<https://www.microsoft.com/wdsi/filesubmission> as "incorrectly detected"; this also helps SmartScreen learn the file.

#### Dependency updates

`.github/dependabot.yml` has Dependabot open grouped pull requests every Monday. One PR covers the GitHub
Actions versions; the other covers the Python packages in `requirements.txt` and `requirements-dev.txt`.
The workflow tests and builds each PR, so merge it once the checks pass.

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest                  # everything: unit tests + web UI tests (about 2 minutes)
python -m pytest -m "not e2e"     # unit tests only (seconds)
```

- **Unit tests:** `tests/test_*.py` cover the parser, sanitizer, redaction, payload highlighting, OWASP mapping,
  profiles, HTML and Word rendering, and the command line.
- **Web UI tests:** `tests/e2e/` starts the app and drives it in Microsoft Edge with Playwright, covering
  previews, every settings panel, the exports, uploads, the security checks and performance. These tests run in
  order and share one page.
  - Set `BURP_REPORT_TEST_BROWSER=chrome` to use Chrome instead.
  - Set `BURP_REPORT_EXE=path\to\exe` to test a built exe.
  - Screenshots of failures go to `test-results/`.

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
  - **Grouping & sorting**, **Summary & text**.
  - **HTTP evidence**: requests/responses, size limits, payload highlighting and secret redaction (see below).
- **Right: live preview.** The report re-renders a moment after each change and keeps your scroll position.
  - **Live HTML** shows the interactive HTML report at desktop, tablet or phone width.
  - **PDF** renders the actual PDF, so you can check page breaks before exporting.

**Export HTML**, **Export Word** and **Export PDF** download the finished report. **Save profile** and **Load profile** use the same JSON
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
| 1 | Output | any of HTML, PDF and Word · output path · search/filter toolbar in the HTML report |
| 2 | Template & styling | built-in or custom template · accent colour · font · page break per finding · export a template to edit |
| 3 | Report details | title, subtitle, client, assessor, company, date, version, classification label, logo |
| 4 | Sections | cover, contents, executive summary, scope, risk chart, findings table, hosts table, OWASP Top 10 mapping, detailed findings, appendix |
| 5 | Finding fields | description, issue detail, detail items, remediation, references, CWE/CAPEC, CWE & OWASP category, affected URLs, evidence |
| 6 | Filters | severities, confidence levels, hosts, individual issue types (e.g. to drop false positives) |
| 7 | Grouping & sorting | group instances by issue type or list each one · sort order · finding ID prefix |
| 8 | Evidence | requests and/or responses · headers only · size limit · payload highlighting · secret redaction and extra values to redact · max instances per finding |
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
`-f` takes `html`, `pdf`, `docx`, `both` (HTML + PDF), `all`, or a comma list such as `-f html,docx`.

## Evidence: payload highlighting and redaction

- **Payload highlighting** (on by default). Burp names the payload in each issue's detail ("The payload `…` was
  submitted"); the report marks where it appears in the request and response, whether raw, URL-encoded or
  HTML-encoded. Distinctive values such as a reflected origin or disclosed e-mail addresses are marked too.
  One- or two-character payloads (e.g. `'`) are only marked in the request.
- **Redaction** (on by default) masks secrets as `[REDACTED]` in evidence and URLs: all cookie values
  (`Cookie`, `Set-Cookie`), `Authorization` credentials, headers such as `X-Api-Key` / `X-CSRF-Token`, parameters and
  JSON keys named like passwords, tokens, keys, sessions or CSRF values, hidden CSRF inputs, JWTs, private-key blocks
  and common cloud/API key formats. Add your own under **Extra values to redact**: one per line, literal text, or
  `/regex/` (`/regex/i` to ignore case). The appendix states how many values were masked. Only the report is
  changed; the Burp file is untouched. Issue descriptions written by Burp are not redacted.

## OWASP Top 10 and CWE

Burp's export lists the CWEs for each issue. The report shows them per finding, adds a CWE column to the findings
table, and includes an **OWASP Top 10 (2021) mapping** section. That section is a table of the ten categories with
severity counts and links to the matching findings, plus a "Not mapped" row. The mapping uses OWASP's published CWE
lists for each category, bundled in `burp_report/owasp.py`; a finding can fall into more than one category.

## Word export

The `.docx` follows the chosen template's colours and section/field settings. It includes a contents list
(Word fills in page numbers when it updates fields on opening; it asks first), "Page X of Y" footers,
linked finding IDs, and highlighted payloads in the evidence. Word can't use the web fonts embedded in HTML and PDF
reports, so each template uses fonts that come with Office: Corporate uses Cambria and Calibri, Modern uses Segoe UI,
and Minimal uses Arial. SVG and WebP logos aren't supported in Word; use PNG or JPG.

## Templates

Three templates are built in:

- **corporate**: navy accent, numbered sections; Source Serif 4 headings with Source Sans 3 body text
- **modern**: gradient cover, finding cards, side navigation in HTML; Inter throughout
- **minimal**: compact, monochrome and printer-friendly; IBM Plex Sans

Request/response evidence uses JetBrains Mono in every template.

### Fonts

The fonts above ship in `burp_report/fonts/` (Latin subset, variable weights, SIL Open Font License; the
licence texts sit next to each font file). A report embeds only the fonts it uses, as data URIs, so exported HTML
and PDF look the same on any machine, offline included. This adds roughly 115–160 KB to an HTML report. Characters
outside the Latin subset (e.g. Japanese) fall back to the system fonts in the stack.

To use a bundled font in your own template or in the **Font** option, refer to it by name: `"Inter"`,
`"Source Sans 3"`, `"Source Serif 4"`, `"IBM Plex Sans"` or `"JetBrains Mono"`.

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
  redact.py               secret redaction for evidence
  highlight.py            payload highlighting in evidence
  owasp.py                CWE → OWASP Top 10 (2021) mapping
  docx_export.py          Word (.docx) export
  pdf.py                  HTML → PDF (Edge/Chrome headless, WeasyPrint fallback)
  cli.py                  terminal wizard and command-line options
  web.py                  local web UI server (stdlib only)
  webui/index.html        web UI (single file, works offline)
  fonts/                  bundled OFL fonts embedded into reports
  templates/              _common/ (shared) + corporate/ modern/ minimal/
samples/sample_burp_export.xml
tests/                    unit tests; e2e/ holds the web UI tests
packaging/                PyInstaller spec, icon
.github/                  build/release workflow and Dependabot config
```

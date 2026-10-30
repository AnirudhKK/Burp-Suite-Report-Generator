# Burp Suite Report Generator

[![Build and release](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/actions/workflows/build-exe.yml/badge.svg)](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/actions/workflows/build-exe.yml)
[![Latest release](https://img.shields.io/github/v/release/AnirudhKK/Burp-Suite-Report-Generator)](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/burp-report-generator)](https://pypi.org/project/burp-report-generator/)
[![Python](https://img.shields.io/pypi/pyversions/burp-report-generator)](https://pypi.org/project/burp-report-generator/)
[![CodeQL](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/actions/workflows/codeql.yml/badge.svg)](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/AnirudhKK/Burp-Suite-Report-Generator/badge)](https://scorecard.dev/viewer/?uri=github.com/AnirudhKK/Burp-Suite-Report-Generator)
[![Docs](https://img.shields.io/badge/docs-online-indigo)](https://anirudhkk.github.io/Burp-Suite-Report-Generator/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/LICENSE)

Turn a **Burp Suite Professional XML export** into a polished, client-ready security report in **HTML**,
**PDF** or **Word**. You design it in a local web app with a live preview, or generate it from the command line.

- **Three templates** (Corporate, Modern, Minimal) with your own accent colour, fonts and logo, or build your own.
- **Choose what goes in:** sections, finding fields, severity/confidence/host filters, and issue types to drop.
- **HTTP evidence** with the attack payload highlighted, and secrets automatically redacted.
- **OWASP Top 10:2025 and CWE** mapping for every finding (the 2021 edition is available as an option).
- **Fully offline:** fonts and mappings are bundled; nothing leaves your machine.

![Burp Report Studio: template and styling settings on the left, live preview of the report on the right](https://raw.githubusercontent.com/AnirudhKK/Burp-Suite-Report-Generator/main/docs/images/studio.png)

| Modern template: findings overview | HTTP evidence: payload highlighted, cookie redacted |
|---|---|
| ![Modern template showing the severity chart and findings table](https://raw.githubusercontent.com/AnirudhKK/Burp-Suite-Report-Generator/main/docs/images/template-modern.png) | ![A finding's request and response with the XSS payload highlighted and the session cookie shown as REDACTED](https://raw.githubusercontent.com/AnirudhKK/Burp-Suite-Report-Generator/main/docs/images/finding-evidence.png) |

Full guide: **[documentation site](https://anirudhkk.github.io/Burp-Suite-Report-Generator/)** (also in [Documentation.md](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/Documentation.md)) · What's new: **[CHANGELOG.md](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/CHANGELOG.md)**

---

## Setup

### Option 1: Python (Windows, macOS, Linux)

Requires Python 3.10+. Install from [PyPI](https://pypi.org/project/burp-report-generator/):

```powershell
pip install burp-report-generator     # or: pipx install burp-report-generator
burp-report                           # opens the web UI in your browser
```

Or run it from source, if you want to change the code or templates:

```powershell
git clone https://github.com/AnirudhKK/Burp-Suite-Report-Generator.git
cd Burp-Suite-Report-Generator
python -m venv .venv
.venv\Scripts\Activate.ps1            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python generate_report.py             # same as burp-report
```

### Option 2: Windows executable (no Python needed)

1. Download `BurpReportGenerator-v<version>.exe` from the [**Releases** page](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/latest).
2. Double-click it. The web UI opens in your browser.
3. If Windows shows **"Windows protected your PC"**, click **More info → Run anyway** (the exe isn't
   code-signed).

To check the download, compare its hash with the release's `.sha256` file. To also prove that GitHub Actions
built it from this repository's source, use the [GitHub CLI](https://cli.github.com/):

```powershell
(Get-FileHash .\BurpReportGenerator-v1.0.6.exe -Algorithm SHA256).Hash
gh attestation verify BurpReportGenerator-v1.0.6.exe --repo AnirudhKK/Burp-Suite-Report-Generator
```

PDF export uses Microsoft Edge or Google Chrome on your PC. Edge ships with Windows, so this usually needs nothing
extra.

## Build

Build the exe and the Python package yourself:

```powershell
pip install -r requirements-dev.txt
pyinstaller packaging/BurpReportGenerator.spec --noconfirm --clean   # dist\BurpReportGenerator-v<version>.exe
python -m build                                                      # dist\*.whl and dist\*.tar.gz
```

GitHub Actions builds and tests both on every push, and records signed build provenance for them. To publish
a release, bump `__version__` in `burp_report/__init__.py` and commit. Then tag and push; this publishes the
GitHub Release and the PyPI package:

```powershell
git tag v1.1.0
git push origin v1.1.0
```

## Test

```powershell
pip install -r requirements-dev.txt
python -m pytest                      # all tests: unit + web UI in Edge (about 2 minutes)
python -m pytest -m "not e2e"         # unit tests only (seconds)
python -m pytest -m "not e2e" --cov   # unit tests with a coverage report
ruff check . ; ruff format --check .  # lint and formatting, as CI runs them
pre-commit install                    # optional: run those checks on every commit
```

## Usage

To get a Burp export: select issues in Burp, right-click, choose **Report selected issues → XML**, and include
requests and responses.

```powershell
python generate_report.py                                  # web UI
python generate_report.py scan.xml                         # web UI with the scan loaded
python generate_report.py scan.xml --cli                   # terminal wizard
python generate_report.py scan.xml -y -f all -t modern --client "Acme" -o reports/acme   # batch
```

Installed from PyPI, use `burp-report` instead of `python generate_report.py`. With the exe, use
`.\BurpReportGenerator-v<version>.exe`.

| Flag | Description |
|---|---|
| `xml` | Burp XML export (required with `-y`) |
| `-y`, `--batch` | No prompts: generate and exit |
| `--cli` | Terminal wizard instead of the web UI |
| `-f`, `--format` | `html`, `pdf`, `docx`, `both` (HTML+PDF), `all`, or a list like `html,docx` |
| `-o`, `--output` | Output path without extension (default: `<xml name>_report`) |
| `-t`, `--template` | `corporate`, `modern`, `minimal`, or a custom template folder |
| `-p`, `--profile` | Load settings from a saved JSON profile |
| `--title`, `--client` | Report title and client name |
| `--min-severity` | `High`, `Medium`, `Low` or `Information` and above |
| `--owasp` | OWASP Top 10 edition: `2025` (default) or `2021` |
| `--port`, `--no-browser` | Web UI port; don't open the browser |
| `--list-templates` | List built-in templates |
| `--export-template NAME DEST` | Copy a template to edit |
| `--version`, `-h` | Version; help |

Command-line flags override profile values. See [Documentation.md](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/Documentation.md#6-command-line-reference)
for the web UI, the wizard and every profile setting.

## Create your own template

1. Copy a built-in template:
   ```powershell
   python generate_report.py --export-template corporate my_template
   ```
2. Edit `my_template/report.html.j2`. Change CSS variables such as `--accent`, `--font` and `--heading-font`, or
   override a section block such as `{% block cover %}`. Templates are [Jinja2](https://jinja.palletsprojects.com/).
3. Use it:
   ```powershell
   python generate_report.py scan.xml -t my_template
   ```
   In the web UI, use **Template & styling → Custom template folder** instead.

[Documentation.md](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/Documentation.md#13-making-your-own-template) lists every block, CSS variable and template
variable.

## Security notes

- **Untrusted content:** Burp's issue HTML can contain content from the scanned target. It's sanitized with an
  allow-list, and HTTP evidence is always escaped.
- **Secrets:** evidence is **redacted by default**. Cookies, auth headers, tokens, passwords, API keys and JWTs
  are masked, and you can add your own values or regexes.
- **XML:** the parser doesn't resolve external entities (XXE).
- **Web UI:** it listens only on `127.0.0.1`. It requires a per-run token, rejects foreign `Host` headers and
  runs under a strict Content Security Policy.
- **Privacy:** no data is sent anywhere. Everything, including PDF rendering, happens locally.

Found a vulnerability? Please report it privately; see [SECURITY.md](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/SECURITY.md).

## Layout

```text
generate_report.py        launcher
burp_report/              the application
  parser.py               Burp XML parsing
  render.py               filtering, grouping, HTML rendering
  docx_export.py          Word export
  pdf.py                  PDF via Edge/Chrome
  redact.py, highlight.py, owasp.py, sanitize.py
  cli.py, web.py          command line and web UI server
  webui/, templates/, fonts/, samples/
tests/                    unit tests + e2e/ web UI tests
docs/                     screenshots, the docs-site hook, make_screenshots.py
mkdocs.yml                documentation site settings
packaging/                PyInstaller spec and icon
pyproject.toml            PyPI package definition
.github/                  build/release, docs, CodeQL and Scorecard workflows, Dependabot, issue templates
Documentation.md          full guide
CHANGELOG.md              release history
SECURITY.md               how to report vulnerabilities
```

## License

[MIT](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/blob/main/LICENSE). The bundled fonts are licensed separately under the SIL Open Font License 1.1; each
font's licence text is next to it in `burp_report/fonts/`.

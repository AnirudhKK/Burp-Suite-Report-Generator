# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Download releases from the
[Releases page](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases).

## [Unreleased]

### Added
- **Documentation site** on GitHub Pages: <https://anirudhkk.github.io/Burp-Suite-Report-Generator/>. It is built
  from `README.md`, `Documentation.md`, `CHANGELOG.md` and `SECURITY.md`, so there is still only one copy of each.
- **Screenshots** of the web UI and reports in the README and the documentation. `docs/make_screenshots.py`
  regenerates them from the sample scan.
- **Ruff** lint and format checks, run in CI by a new **lint** job, and a `pre-commit` configuration that runs
  them on each commit.
- **Test coverage:** CI shows a coverage table on each run's summary page and fails if coverage drops below 70%.
- **OpenSSF Scorecard** workflow, which rates the repository's security practices, with a README badge.

### Fixed
- The web UI could intermittently show **Preview failed** on Windows when several requests reached the local
  server at once. The server now queues up to 128 waiting connections instead of 5.

### Changed
- All Python code formatted with Ruff. Behaviour is unchanged.

## [1.0.6] - 2026-10-31

### Added
- **PyPI package** `burp-report-generator`. Install it with `pip install burp-report-generator` (or `pipx`) and
  run it with `burp-report` on Windows, macOS or Linux. Python 3.10+ is required.
- Version tags publish the package to PyPI automatically, using Trusted Publishing, so no token is stored.
- The wheel and source archive are also attached to each GitHub Release.
- **Signed build provenance** for the exe, the wheel and the source archive. Check any download with
  `gh attestation verify <file> --repo AnirudhKK/Burp-Suite-Report-Generator`.
- CI runs the unit tests on Linux with Python 3.10 and 3.14.
- CI installs the built package into a clean environment and generates reports with it.

### Changed
- The sample scan moved to `burp_report/samples/`, so it ships with the package and **Try the sample report**
  works in every install.
- The workflow is now named **Build and release**.

## [1.0.5] - 2026-10-30

### Added
- MIT licence (`LICENSE`). The bundled fonts stay under the SIL Open Font License.
- `SECURITY.md` explaining how to report vulnerabilities privately.
- Issue templates for bug reports and feature requests. They remind reporters never to attach real client data.
- CodeQL code scanning for the Python code and the GitHub Actions workflows, on every push and weekly.

### Changed
- GitHub Actions updated to their Node.js 24 versions, which removes the "Node.js 20 is deprecated" warning.
  Each action is now pinned to an exact commit.

## [1.0.4]

### Added
- OWASP Top 10:2025 mapping, now the default. The 2021 edition can still be chosen in the web UI
  (**Sections → OWASP Top 10 edition**), in the terminal wizard, with `--owasp 2021`, or with
  `"owasp_edition"` in a profile.
- Report headings and per-finding tags name the edition, e.g. "OWASP Top 10:2025 mapping" and
  `A05:2025 Injection`.
- Automated tests: unit tests, plus browser tests of the web UI in Microsoft Edge. They run in GitHub Actions
  before every build, and again against the built exe.
- Dependabot pull requests every week for GitHub Actions and Python packages.
- Release notes cover the SmartScreen prompt and how to verify the download's SHA-256 checksum.
- `Documentation.md`: a full guide, while `README.md` is now a short quick start.

### Fixed
- The redaction count no longer counts already-masked header values a second time.

### Changed
- Documentation-only pushes no longer start a build.

## [1.0.1] – [1.0.3]

### Added
- GitHub Actions builds the Windows exe, smoke-tests it, and publishes it with a checksum when a version tag is
  pushed.
- The exe's name and Windows version details come from `__version__`.

## [1.0.0]

### Added
- First release.
- Converts Burp Suite Professional XML issue exports into HTML, PDF and Word reports.
- Burp Report Studio, a local web UI with live HTML and PDF preview. There is also a terminal wizard and a batch
  mode.
- Three templates (Corporate, Modern, Minimal) with bundled fonts, accent colours, logos and custom templates.
- Sections, finding fields, filters, grouping and sorting, all saved as JSON profiles.
- HTTP evidence with payload highlighting and redaction of secrets (on by default).
- CWE and OWASP Top 10 mapping.
- A single-file Windows exe that needs no Python.

[Unreleased]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/compare/v1.0.6...HEAD
[1.0.6]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/tag/v1.0.6
[1.0.5]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/tag/v1.0.5
[1.0.4]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/tag/v1.0.4
[1.0.1] – [1.0.3]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases
[1.0.0]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases

# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Download releases from the
[Releases page](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases).

## [Unreleased]

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

[Unreleased]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/tag/v1.0.5
[1.0.4]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/tag/v1.0.4
[1.0.1] – [1.0.3]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases
[1.0.0]: https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases

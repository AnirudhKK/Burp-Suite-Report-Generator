# Security policy

Burp Suite Report Generator handles penetration-test data, so security reports are taken seriously.

## Supported versions

Only the [latest release](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/releases/latest) receives
security fixes. Please check that a problem still exists in the latest release before reporting it.

## Reporting a vulnerability

**Please don't open a public issue for security problems.** Report them privately instead:

1. Go to the repository's **[Security → Advisories](https://github.com/AnirudhKK/Burp-Suite-Report-Generator/security/advisories/new)** page.
2. Click **Report a vulnerability** and describe:
   - what an attacker can do, and under what conditions;
   - the steps to reproduce it, ideally with a minimal crafted Burp XML file;
   - the version (`--version`) and whether you used the exe or Python.

You'll get an acknowledgement within 7 days. A fix and advisory follow once the problem is confirmed, and you'll
be credited unless you'd rather not be.

**Never attach real client data.** Don't include a real scan export, report or profile. Build a minimal example
with made-up hosts and values instead.

## In scope

- **Content from the scanned target escaping into a report.** For example, script execution in an HTML report,
  the web UI preview or the PDF renderer.
- **Redaction failures.** Secrets that the [documented redaction rules](Documentation.md#9-evidence-payload-highlighting-and-redaction)
  should catch appearing unmasked.
- **XML parsing issues**, such as XXE or entity-expansion attacks.
- **The local web UI server** being reachable or usable from other websites or other machines. This includes
  token, Host-header and Content-Security-Policy bypasses.
- **Path traversal or file writes outside the chosen output location.**
- **Tampering with the build or release process**, or the published exe.

## Out of scope

- **SmartScreen and antivirus warnings** about the unsigned exe. These are expected; see the
  [documentation](Documentation.md#2-installation).
- **Attacks that need control of the user's own machine or account.**
- **Findings in Burp Suite itself**, or in the target applications in a scan.

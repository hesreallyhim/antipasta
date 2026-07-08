# Security Policy

## Supported Versions

Security updates are provided for the latest released version of antipasta.
Older versions are not actively maintained, and users should upgrade before
reporting an issue unless the vulnerability also affects the latest release.

| Version | Supported |
| ------- | --------- |
| Latest released version | Yes |
| Older versions | No |

## Reporting a Vulnerability

Please do not report suspected vulnerabilities in public GitHub issues.

Use GitHub's private vulnerability reporting for this repository if it is
available. If private vulnerability reporting is unavailable, email the
maintainer at <hesreallyhim@proton.me>.

When reporting a vulnerability, include:

- the affected antipasta version
- the operating system and Python version used to reproduce the issue
- a clear description of the impact
- reproduction steps, proof-of-concept input, or a minimal affected project
- whether the issue appears to affect the latest released version

The maintainer will review reports on a best-effort basis. You can usually
expect an initial response within 7 days, but complex issues may take longer to
validate and fix. If the report is accepted, the fix will normally be released
in the next suitable patch or minor release. If the report is declined, the
maintainer will explain why when practical.

## Scope

Security reports are most useful when they affect antipasta itself, including:

- unintended command execution
- unsafe handling of project files, paths, or generated reports
- disclosure of local files or sensitive data
- dependency vulnerabilities with a practical impact on antipasta users
- integrity issues in packaging, release, or CI automation

General code-quality findings, false positives in metrics output, or issues in
third-party projects analyzed by antipasta should be reported as regular GitHub
issues instead.

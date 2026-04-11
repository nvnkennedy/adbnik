# Security Policy

## Distribution and trust

**Primary delivery is PyPI** (`pip install adbsshdeck`) — standard Python package signing chain.

Optional **standalone `.exe`** files (if you build them) should ideally be **Authenticode-signed** for SmartScreen. **Open-source projects** can use [SignPath Foundation](https://signpath.org/) or **`docs/WINDOWS_CODE_SIGNING.md`** / **`scripts/sign_windows_artifacts.ps1`** with your own certificate.

## Supported Versions

Security fixes are provided for the latest stable release.

## Reporting a Vulnerability

Please do not open public issues for sensitive vulnerabilities.

Instead, report privately with:
- affected version
- impact summary
- reproduction details
- suggested fix (if known)

Response targets:
- initial response: within 7 days
- status update: within 14 days

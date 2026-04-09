# Security Policy

## Windows installers and trust

Public releases distributed as `.exe` should ideally be **Authenticode-signed** so SmartScreen and corporate policies treat them as legitimate. **Open-source projects can apply for free signing** through [SignPath Foundation](https://signpath.org/) (no certificate purchase). If you buy your own certificate, use **`docs/WINDOWS_CODE_SIGNING.md`** and **`scripts/sign_windows_artifacts.ps1`**.

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

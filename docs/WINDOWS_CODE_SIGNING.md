# Windows code signing (Authenticode)

Unsigned `.exe` files are commonly flagged by **Microsoft SmartScreen** and are **often blocked in enterprise environments** (Software Restriction Policies, Defender Application Control, or “only signed installers” rules). Website text cannot remove those protections; **Authenticode signing** is how legitimate Windows software establishes trust.

## No budget? Free signing for open-source projects

If you cannot buy a certificate, **[SignPath Foundation](https://signpath.org/)** offers **free code signing for qualifying open-source projects**. Signing happens in their infrastructure; binaries are verified against your public repository. Apply through their site and follow their CI integration docs. This is the most practical path to **trusted Windows binaries without a personal certificate purchase**.

---

## Commercial certificate (optional)

This section applies if you purchase your own certificate instead.

### What you need

1. A **code signing certificate** from a publicly trusted Certificate Authority (DigiCert, Sectigo, SSL.com, etc.).
2. **Windows SDK** (includes `signtool.exe`) or Visual Studio “Desktop development with C++” workload.
3. Optional: **Inno Setup** if you build the installer with `DeviceDeck.iss`.

Certificate types:

- **Standard code signing** — Works with SmartScreen over time as reputation builds; may still show warnings briefly for new files.
- **Extended Validation (EV)** — Often faster SmartScreen trust; requires a hardware token (USB) for the key in many setups.

Purchase and identity verification are handled by the CA; budget and turnaround vary by vendor.

## Sign after building (your own .pfx certificate)

If you use **SignPath**, follow their project setup instead of the steps below.

Build the app and installer first (`scripts/build_windows_exe.ps1`, then compile the Inno Setup script). Then sign **in this order**:

1. `dist\DeviceDeck\DeviceDeck.exe` (main executable)
2. Re-create the portable ZIP if it must contain the signed EXE
3. `dist_installer\DeviceDeck_Setup_<version>.exe` (installer)

Use the helper script (from repo root):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_windows_artifacts.ps1 `
  -PfxPath "C:\certs\your_codesign.pfx" `
  -PfxPassword (Read-Host -AsSecureString)
```

Or set environment variables `DEVICE_DECK_PFX` and `DEVICE_DECK_PFX_PASSWORD` (avoid committing secrets).

### Manual `signtool` example

Find `signtool` under `C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64\signtool.exe`.

```powershell
$st = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
& $st sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f your.pfx /p "password" "dist\DeviceDeck\DeviceDeck.exe"
& $st sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f your.pfx /p "password" "dist_installer\DeviceDeck_Setup_0.1.0.exe"
```

Timestamping (`/tr`) keeps signatures valid after the certificate expires.

## Inno Setup integration

You can sign inside Inno Setup via **Tools → Configure Sign Tools**, or rely on signing the generated `DeviceDeck_Setup_*.exe` **after** `ISCC` (simpler for automation). If you sign inside Inno, enable **Signed uninstaller** for a fully signed experience.

## After signing: website and releases

1. Copy the **signed** files into `site/downloads/` and update `site/config.js`.
2. Set **`authenticodeSigned: true`** in `site/config.js` only when the published files are actually signed.
3. Run `scripts/compute_release_hashes.ps1` and paste SHA-256 values into `config.js` so IT teams can verify files.
4. Upload the same signed assets to GitHub Releases if you use them.

## References

- [Microsoft: SignTool](https://learn.microsoft.com/windows/win32/seccrypto/signtool)
- [SmartScreen and reputation](https://learn.microsoft.com/windows/security/threat-protection/microsoft-defender-smartscreen/microsoft-defender-smartscreen-overview)

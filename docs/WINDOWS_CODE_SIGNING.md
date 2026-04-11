# Windows code signing (Authenticode)

Unsigned `.exe` files are commonly flagged by **Microsoft SmartScreen** and are **often blocked in enterprise environments** (Software Restriction Policies, Defender Application Control, or “only signed installers” rules). Website text cannot remove those protections; **Authenticode signing** is how legitimate Windows software establishes trust.

## Why it feels unfair (and why Windows does this)

**Microsoft does not hand out free “trusted publisher” certificates to every developer.** If they did, malware authors could sign fake apps and look as legitimate as real software. So **trust** is delegated to **certificate authorities (CAs)** that **verify identity** (individual or company) before issuing a cert. That verification costs money, which is why retail code-signing certs are paid products.

**SignTool** (from the Windows SDK) is free, but it only **applies** a signature. It does **not** include a certificate. **Self-signing** with a homemade certificate does **not** satisfy SmartScreen for the general public.

This design is **strict on purpose** (reduce drive-by malware), not because small projects are unwanted. The practical **free** path for open source is **third-party OSS programs** (below) that pay for or donate CA-backed signing after checking your source.

**No one else can “flip a switch” in your repo** to make Windows trust your EXE: signing requires either **your certificate**, **your approval** on a service like SignPath, or **your** CI secrets. This document and the website can only explain the path.

## No budget? Free signing for open-source projects

If you cannot buy a certificate, **[SignPath Foundation](https://signpath.org/)** offers **free code signing for qualifying open-source projects**. Signing happens in their infrastructure; binaries are verified against your public repository.

**Step-by-step (account, GitHub App, secrets, Actions):** see **[SIGNPATH_SETUP.md](./SIGNPATH_SETUP.md)** in this repo — only you can complete the SignPath registration.

**What you do (high level — details are on their site):**

1. **Apply** at [signpath.org](https://signpath.org/) and create a project linked to your **public** GitHub repository.
2. **Define** which build artifacts may be signed (policy) so only builds produced from your repo get signed.
3. **Upload** a release build through their UI, or connect **GitHub Actions** with their documented integration so CI submits the built `.exe` / installer for signing.
4. **Publish** the **signed** files (e.g. attach to a GitHub Release). Primary user distribution is **PyPI** (`pip install adbnik`), not checked-in installers.

If SignPath declines or your project does not qualify yet, the fallback remains: **community unsigned builds** and users using **More info → Run anyway** on their own PCs, or **purchasing** a certificate later.

This is the most practical path to **CA-trusted Windows binaries without buying a personal certificate**.

---

## Commercial certificate (optional)

This section applies if you purchase your own certificate instead.

### What you need

1. A **code signing certificate** from a publicly trusted Certificate Authority (DigiCert, Sectigo, SSL.com, etc.).
2. **Windows SDK** (includes `signtool.exe`) or Visual Studio “Desktop development with C++” workload.
3. Optional: **Inno Setup** if you build the installer with `adbnik.iss`.

Certificate types:

- **Standard code signing** — Works with SmartScreen over time as reputation builds; may still show warnings briefly for new files.
- **Extended Validation (EV)** — Often faster SmartScreen trust; requires a hardware token (USB) for the key in many setups.

Purchase and identity verification are handled by the CA; budget and turnaround vary by vendor.

## Sign after building (your own .pfx certificate)

If you use **SignPath**, follow their project setup instead of the steps below.

Build the app and installer first (`scripts/build_windows_exe.ps1`, then compile the Inno Setup script). Then sign **in this order**:

1. `dist\Adbnik\Adbnik.exe` (main executable)
2. Re-create the portable ZIP if it must contain the signed EXE
3. `dist_installer\Adbnik_Setup_<version>.exe` (installer)

Use the helper script (from repo root):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_windows_artifacts.ps1 `
  -PfxPath "C:\certs\your_codesign.pfx" `
  -PfxPassword (Read-Host -AsSecureString)
```

Or set environment variables `ADBNIK_PFX` and `ADBNIK_PFX_PASSWORD` (avoid committing secrets).

### Manual `signtool` example

Find `signtool` under `C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64\signtool.exe`.

```powershell
$st = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
& $st sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f your.pfx /p "password" "dist\Adbnik\Adbnik.exe"
& $st sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f your.pfx /p "password" "dist_installer\Adbnik_Setup_0.2.0.exe"
```

Timestamping (`/tr`) keeps signatures valid after the certificate expires.

## Inno Setup integration

You can sign inside Inno Setup via **Tools → Configure Sign Tools**, or rely on signing the generated `Adbnik_Setup_*.exe` **after** `ISCC` (simpler for automation). If you sign inside Inno, enable **Signed uninstaller** for a fully signed experience.

## After signing: releases

1. Attach **signed** artifacts to a **GitHub Release** (optional) or distribute through your own channel.
2. Primary app delivery for users is **`pip install adbnik`** on PyPI — unsigned/signed Windows bundles are optional extras for people without Python.

## References

- [Microsoft: SignTool](https://learn.microsoft.com/windows/win32/seccrypto/signtool)
- [SmartScreen and reputation](https://learn.microsoft.com/windows/security/threat-protection/microsoft-defender-smartscreen/microsoft-defender-smartscreen-overview)

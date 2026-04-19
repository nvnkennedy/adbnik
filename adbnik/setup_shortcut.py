"""Windows: create a Start Menu / Desktop-style shortcut to Adbnik with the app icon.

Run after ``pip install adbnik``::

    adbnik-setup

This is separate from ``pip`` itself (pip cannot create shortcuts or pick folders).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _escape_ps_single_quoted(s: str) -> str:
    """Escape for PowerShell single-quoted string."""
    return s.replace("'", "''")


def _windows_desktop_folder() -> Path:
    if sys.platform != "win32":
        return Path.home() / "Desktop"
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOP = 0x10
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
            return Path(buf.value)
    except Exception:
        pass
    return Path.home() / "Desktop"


def _icon_cache_file() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    d = Path(base) / "Adbnik"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d / "adbnik-shortcut.ico"


def _ensure_shortcut_icon_file() -> str:
    """Write the same rendered icon as the app uses; return path for .lnk IconLocation."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True
    try:
        from .ui.app_icon import create_app_icon

        path = _icon_cache_file()
        icon = create_app_icon(dark=True)
        pm = icon.pixmap(256, 256)
        ok = pm.save(str(path), "ICO")
        if not ok:
            ok = pm.save(str(path.with_suffix(".png")), "PNG")
            if ok:
                path = path.with_suffix(".png")
        if not ok:
            return ""
        return str(path.resolve())
    finally:
        if created:
            try:
                app.quit()
            except Exception:
                pass


def _write_shortcut_ps1(
    *,
    lnk_path: Path,
    target_exe: str,
    arguments: str,
    work_dir: str,
    icon_path: str,
) -> str:
    """Return PowerShell script body (UTF-8)."""
    lines = [
        "$WshShell = New-Object -ComObject WScript.Shell",
        f"$Shortcut = $WshShell.CreateShortcut('{_escape_ps_single_quoted(str(lnk_path))}')",
        f"$Shortcut.TargetPath = '{_escape_ps_single_quoted(target_exe)}'",
        f"$Shortcut.Arguments = '{_escape_ps_single_quoted(arguments)}'",
        f"$Shortcut.WorkingDirectory = '{_escape_ps_single_quoted(work_dir)}'",
    ]
    if icon_path:
        lines.append(f"$Shortcut.IconLocation = '{_escape_ps_single_quoted(icon_path)},0'")
    lines.append("$Shortcut.Save()")
    return "\r\n".join(lines) + "\r\n"


def _run_powershell_script(script: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".ps1",
        delete=False,
        encoding="utf-8-sig",
        newline="",
    ) as f:
        f.write(script)
        ps1 = f.name
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ps1,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
            raise RuntimeError(err)
    finally:
        try:
            os.unlink(ps1)
        except OSError:
            pass


def _pick_folder_gui(start_dir: Path) -> Path | None:
    from PyQt5.QtWidgets import QFileDialog, QApplication

    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True
    try:
        d = QFileDialog.getExistingDirectory(
            None,
            "Choose folder for the Adbnik shortcut",
            str(start_dir),
        )
        if not d:
            return None
        return Path(d)
    finally:
        if created:
            try:
                app.quit()
            except Exception:
                pass


def main() -> None:
    if sys.platform != "win32":
        print("adbnik-setup: only supported on Windows.", file=sys.stderr)
        sys.exit(2)

    p = argparse.ArgumentParser(
        description="Create an Adbnik shortcut (same Python as this command) with the app icon.",
    )
    p.add_argument(
        "--folder",
        metavar="DIR",
        help="Folder for Adbnik.lnk (default: ask with a folder dialog, starting on Desktop)",
    )
    p.add_argument(
        "--name",
        default="Adbnik",
        help="Shortcut file name without .lnk (default: Adbnik)",
    )
    args = p.parse_args()

    py_exe = Path(sys.executable).resolve()
    work_dir = str(py_exe.parent)
    target = str(py_exe)
    launch_args = "-m adbnik"

    icon_path = ""
    try:
        icon_path = _ensure_shortcut_icon_file()
    except Exception:
        icon_path = ""

    desktop = _windows_desktop_folder()
    if args.folder:
        folder = Path(args.folder).expanduser().resolve()
    else:
        chosen = _pick_folder_gui(desktop)
        if chosen is None:
            print("Cancelled.")
            sys.exit(1)
        folder = chosen

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Cannot use folder: {exc}", file=sys.stderr)
        sys.exit(1)

    name = (args.name or "Adbnik").strip() or "Adbnik"
    if not name.lower().endswith(".lnk"):
        name = f"{name}.lnk"
    lnk = folder / name

    script = _write_shortcut_ps1(
        lnk_path=lnk,
        target_exe=target,
        arguments=launch_args,
        work_dir=work_dir,
        icon_path=icon_path,
    )
    try:
        _run_powershell_script(script)
    except Exception as exc:
        print(f"Failed to create shortcut: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Shortcut created:\n  {lnk}")

    # After GUI folder picker, confirm in a dialog; with --folder, stay console-only.
    if not args.folder:
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            created = False
            if app is None:
                app = QApplication(sys.argv)
                created = True
            try:
                QMessageBox.information(
                    None,
                    "Adbnik",
                    f"Shortcut created:\n{lnk}",
                )
            finally:
                if created:
                    app.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()

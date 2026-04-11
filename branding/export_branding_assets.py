"""Generate PNG + ICO under branding/ for README, PyPI, and GitHub Pages.

Run from repo root:  py -m pip install -e .  &&  py branding/export_branding_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import QApplication

from adbnik.ui.app_icon import create_app_icon


def main() -> None:
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parent

    for fname, dark in (
        ("adbnik-256.png", True),
        ("adbnik-256-light.png", False),
    ):
        icon = create_app_icon(dark=dark)
        pm = icon.pixmap(256, 256)
        out = root / fname
        if not pm.save(str(out), "PNG"):
            raise SystemExit(f"Failed to write {out}")
        print(f"Wrote {out}")

    icon = create_app_icon(dark=True)
    pm = icon.pixmap(48, 48)
    out = root / "favicon.ico"
    if not pm.save(str(out), "ICO"):
        raise SystemExit(f"Failed to write {out}")
    print(f"Wrote {out}")

    app.quit()


if __name__ == "__main__":
    main()

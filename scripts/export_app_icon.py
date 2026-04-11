"""Write assets/adbnik.ico (dark, for PyInstaller) and assets/adbnik_light.ico (reference)."""

from pathlib import Path

from PyQt5.QtWidgets import QApplication

from adbnik.ui.app_icon import create_app_icon


def main() -> None:
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    for name, dark in (("adbnik.ico", True), ("adbnik_light.ico", False)):
        out = assets / name
        icon = create_app_icon(dark=dark)
        if not icon.pixmap(256, 256).save(str(out), "ICO"):
            raise RuntimeError(f"Failed to write: {out}")
        print(f"Wrote {out} ({'dark' if dark else 'light'} theme)")

    print("Note: adbnik.spec uses assets/adbnik.ico (dark) for the Windows exe installer.")
    app.quit()


if __name__ == "__main__":
    main()

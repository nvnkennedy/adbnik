from pathlib import Path

from PyQt5.QtWidgets import QApplication

from devicedeck.ui.app_icon import create_app_icon


def main() -> None:
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    out = root / "assets" / "devicedeck.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    icon = create_app_icon()
    if not icon.pixmap(256, 256).save(str(out), "ICO"):
        raise RuntimeError(f"Failed to write icon file: {out}")
    print(f"Wrote icon: {out}")
    app.quit()


if __name__ == "__main__":
    main()

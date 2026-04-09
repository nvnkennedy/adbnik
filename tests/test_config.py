"""Config load/save behavior (no GUI)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def test_load_ignores_unknown_keys(tmp_path):
    from devicedeck.config import AppConfig

    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps(
            {
                "adb_path": r"C:\tools\adb.exe",
                "dark_theme": True,
                "future_app_field_should_be_ignored": {"x": 1},
            }
        ),
        encoding="utf-8",
    )
    with patch("devicedeck.config.CONFIG_PATH", p):
        cfg = AppConfig.load()
    assert cfg.adb_path == r"C:\tools\adb.exe"
    assert cfg.dark_theme is True


def test_save_roundtrip_respects_known_fields(tmp_path):
    from devicedeck.config import AppConfig

    p = tmp_path / "cfg.json"
    with patch("devicedeck.config.CONFIG_PATH", p):
        c = AppConfig(adb_path=r"Z:\adb", dark_theme=True)
        c.save()
        c2 = AppConfig.load()
    assert c2.adb_path == r"Z:\adb"
    assert c2.dark_theme is True
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "future_app_field_should_be_ignored" not in raw


def test_import_entrypoint():
    from devicedeck.app import main

    assert callable(main)

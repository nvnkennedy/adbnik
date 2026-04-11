import json
from pathlib import Path
from unittest.mock import patch


def test_config_roundtrip(tmp_path: Path) -> None:
    from adbnik.config import AppConfig

    p = tmp_path / "cfg.json"
    with patch("adbnik.config.CONFIG_PATH", p):
        c = AppConfig(adb_path="/x/adb", dark_theme=True)
        c.save()
        loaded = AppConfig.load()
    assert loaded.adb_path == "/x/adb"
    assert loaded.dark_theme is True


def test_config_ignores_unknown_keys(tmp_path: Path) -> None:
    from adbnik.config import AppConfig

    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"adb_path": "a", "future_field": 1}), encoding="utf-8")
    with patch("adbnik.config.CONFIG_PATH", p):
        loaded = AppConfig.load()
    assert loaded.adb_path == "a"


def test_main_import() -> None:
    from adbnik.app import main

    assert callable(main)

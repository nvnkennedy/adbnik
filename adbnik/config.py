import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List


# Primary settings file; legacy paths are read once and removed after save when possible.
CONFIG_PATH = Path.home() / ".adbnik.json"
_LEGACY_DEVICEDECK_CONFIG = Path.home() / ".devicedeck.json"
_LEGACY_CONFIG_PATH = Path.home() / ".adb_explorer_pro.json"


def has_existing_config_file() -> bool:
    return (
        CONFIG_PATH.exists()
        or _LEGACY_DEVICEDECK_CONFIG.exists()
        or _LEGACY_CONFIG_PATH.exists()
    )


def _sanitize_bookmark(bookmark: Dict[str, Any]) -> Dict[str, Any]:
    """Drop sensitive fields before keeping bookmark data in config."""
    cleaned = dict(bookmark)
    for key in ("ssh_password", "sftp_password", "ftp_password"):
        cleaned.pop(key, None)
    return cleaned


@dataclass
class AppConfig:
    # Empty on first run; resolved at runtime to "adb"/"scrcpy" when unset.
    adb_path: str = ""
    scrcpy_path: str = ""
    dark_theme: bool = False
    # When True, dock scrcpy into the Screen Control tab (Windows). Default False: separate window keeps
    # reliable touch/swipe (embedded HWND reparenting often breaks input).
    embed_scrcpy_mirror: bool = False
    # Legacy mirror of embed checkbox; kept for older configs (embed off => opt_out true).
    embed_scrcpy_mirror_opt_out: bool = True
    default_ssh_host: str = ""
    default_serial_port: str = "COM3"
    default_serial_baud: str = "115200"
    # Optional SSH: sent to the active terminal when using Commands → SSH (after you open an SSH tab).
    ssh_mount_command: str = ""
    # List of {"label": str, "command": str} — customizable in Preferences.
    ssh_quick_commands: List[Dict[str, str]] = field(default_factory=list)
    # Saved sessions (WinSCP/Moba-style): list of dicts with kind, name, host, user, etc.
    session_bookmarks: List[Dict[str, Any]] = field(default_factory=list)
    # Find files dialog: recent folder paths per side (local vs remote search)
    find_folder_history_local: List[str] = field(default_factory=list)
    find_folder_history_remote: List[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_PATH.exists():
            read_path = CONFIG_PATH
        elif _LEGACY_DEVICEDECK_CONFIG.exists():
            read_path = _LEGACY_DEVICEDECK_CONFIG
        elif _LEGACY_CONFIG_PATH.exists():
            read_path = _LEGACY_CONFIG_PATH
        else:
            return cls()
        known = {f.name for f in fields(cls)}
        try:
            raw = json.loads(read_path.read_text(encoding="utf-8"))
            defaults = asdict(cls())
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key in known:
                        defaults[key] = value
            if not isinstance(defaults.get("session_bookmarks"), list):
                defaults["session_bookmarks"] = []
            else:
                defaults["session_bookmarks"] = [
                    _sanitize_bookmark(x)
                    for x in defaults["session_bookmarks"]
                    if isinstance(x, dict)
                ]
            qc = defaults.get("ssh_quick_commands")
            if not isinstance(qc, list):
                defaults["ssh_quick_commands"] = []
            else:
                defaults["ssh_quick_commands"] = [
                    {"label": str(x.get("label", "")), "command": str(x.get("command", ""))}
                    for x in qc
                    if isinstance(x, dict) and (x.get("label") or x.get("command"))
                ]
            for key in ("find_folder_history_local", "find_folder_history_remote"):
                lst = defaults.get(key)
                if not isinstance(lst, list):
                    defaults[key] = []
                else:
                    defaults[key] = [str(x).strip() for x in lst if str(x).strip()][:40]
            return cls(**defaults)
        except Exception as exc:
            print(f"[Adbnik] Could not load config '{read_path}': {exc}")
            return cls()

    def save(self) -> None:
        data = asdict(self)
        data["session_bookmarks"] = [
            _sanitize_bookmark(x)
            for x in data.get("session_bookmarks", [])
            if isinstance(x, dict)
        ]
        qc = data.get("ssh_quick_commands")
        if isinstance(qc, list):
            data["ssh_quick_commands"] = [
                {"label": str(x.get("label", "")), "command": str(x.get("command", ""))}
                for x in qc
                if isinstance(x, dict) and (str(x.get("label", "")).strip() or str(x.get("command", "")).strip())
            ]
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        path = CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=f"{path.name}.",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        try:
            if _LEGACY_CONFIG_PATH.is_file():
                _LEGACY_CONFIG_PATH.unlink()
        except OSError:
            pass
        try:
            if _LEGACY_DEVICEDECK_CONFIG.is_file():
                _LEGACY_DEVICEDECK_CONFIG.unlink()
        except OSError:
            pass

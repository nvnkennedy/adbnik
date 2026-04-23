"""Parse `adb devices -l` for serial + human-readable device names (e.g. model name)."""

import re
from typing import List, Optional, Tuple

from .commands import run_adb


def infer_scrcpy_keyboard_mode(adb_path: str, serial: str) -> Optional[str]:
    """
    Pick scrcpy ``--keyboard`` for devices where SDK injection often fails (IVI / automotive).

    Returns ``"uhid"`` when props/features suggest automotive or embedded-class builds;
    ``None`` means omit the flag (scrcpy default SDK injection — typical phones).
    """
    serial = (serial or "").strip()
    if not serial:
        return None
    blob = ""
    for cmd in (
        ["shell", "getprop", "ro.build.characteristics"],
        ["shell", "getprop", "ro.hardware"],
        ["shell", "getprop", "ro.product.first_api_level"],
    ):
        code, out, _ = run_adb(adb_path, ["-s", serial, *cmd], timeout=5)
        if code == 0 and out:
            blob += out.lower()
    hints = (
        "automotive",
        "embedded",
        "ivi",
        "android automotive",
        "android.hardware.type.automotive",
        "aaos",
        "vehicle",
        "infotainment",
        "headunit",
        "head unit",
    )
    if any(h in blob for h in hints):
        return "uhid"
    code, out, _ = run_adb(adb_path, ["-s", serial, "shell", "pm", "list", "features"], timeout=8)
    if code == 0 and out:
        ol = out.lower()
        if any(
            x in ol
            for x in (
                "android.hardware.type.automotive",
                "android.hardware.automotive",
                "android.software.cantunnel",
            )
        ):
            return "uhid"
    return None


def _parse_devices_l_line(line: str) -> Optional[Tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("List of devices"):
        return None
    # Match: SERIAL <spaces> device|unauthorized|sideload|recovery (adb uses tabs or spaces)
    m = re.match(r"^(\S+)\s+(device|unauthorized|sideload|recovery)\b", line)
    if not m:
        return None
    serial, state = m.group(1), m.group(2)
    if serial in ("List", "*", "adb"):
        return None

    m2 = re.search(r"\bmodel:([^\s]+)", line)
    model = m2.group(1).replace("_", " ") if m2 else ""
    if not model:
        m3 = re.search(r"\bdevice:([^\s]+)", line)
        model = m3.group(1).replace("_", " ") if m3 else ""
    tag = f" [{state}]" if state != "device" else ""
    if model:
        display = f"{model} · {serial}{tag}"
    else:
        display = f"{serial}{tag}"
    return serial, display


def list_adb_devices(adb_path: str) -> List[Tuple[str, str]]:
    """
    Return [(serial, display_label), ...].
    Lists devices (handles space- or tab-separated lines).
    """
    code, stdout, _ = run_adb(adb_path, ["devices", "-l"])
    out: List[Tuple[str, str]] = []
    if code == 0 and stdout:
        for line in stdout.splitlines():
            parsed = _parse_devices_l_line(line)
            if parsed:
                out.append(parsed)
    if out:
        return out

    code2, stdout2, _ = run_adb(adb_path, ["devices"])
    if code2 != 0:
        return []
    for line in stdout2.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        m = re.match(r"^(\S+)\s+(device|unauthorized|sideload|recovery)\s*$", line)
        if m:
            serial = m.group(1)
            state = m.group(2)
            tag = f" [{state}]" if state != "device" else ""
            out.append((serial, f"{serial}{tag}"))
    return out


def friendly_name_for_serial(adb_path: str, serial: str) -> str:
    """Short name for tabs (e.g. 'Palq'); falls back to serial."""
    if not serial:
        return "ADB"
    for s, display in list_adb_devices(adb_path):
        if s == serial:
            if " · " in display:
                return display.split(" · ", 1)[0].strip()
            return display
    return serial

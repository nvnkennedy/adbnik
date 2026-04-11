"""Windows: global hotkeys to stop scrcpy when the mirror steals focus (e.g. fullscreen)."""

import sys

SCRCPY_HOTKEY_ID = 0x4A42
SCRCPY_HOTKEY_ID2 = 0x4A43

_MOD_CONTROL = 0x0002
_MOD_ALT = 0x0001
_MOD_NOREPEAT = 0x4000
_VK_F12 = 0x7B
_VK_END = 0x23


def _register_one(hwnd: int, hid: int, vk: int) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes

        return bool(
            ctypes.windll.user32.RegisterHotKey(
                int(hwnd), hid, _MOD_CONTROL | _MOD_ALT | _MOD_NOREPEAT, vk
            )
        )
    except Exception:
        return False


def register_scrcpy_stop_hotkey(hwnd: int) -> bool:
    """Register Ctrl+Alt+F12 and Ctrl+Alt+End — either can stop the mirror from anywhere."""
    ok_f12 = _register_one(hwnd, SCRCPY_HOTKEY_ID, _VK_F12)
    ok_end = _register_one(hwnd, SCRCPY_HOTKEY_ID2, _VK_END)
    return bool(ok_f12 or ok_end)


def unregister_scrcpy_stop_hotkey(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(int(hwnd), SCRCPY_HOTKEY_ID)
        user32.UnregisterHotKey(int(hwnd), SCRCPY_HOTKEY_ID2)
    except Exception:
        pass


def is_windows_hotkey_message(event_type, message) -> bool:
    """Return True if this is WM_HOTKEY for one of our scrcpy stop ids."""
    if sys.platform != "win32":
        return False
    try:
        if hasattr(event_type, "data"):
            et = bytes(event_type.data()).decode("latin1", errors="ignore")
        else:
            et = bytes(event_type).decode("latin1", errors="ignore")
    except Exception:
        try:
            et = str(event_type)
        except Exception:
            return False
    if "windows_generic_MSG" not in et and "windows_dispatcher_MSG" not in et:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        if msg.message != 0x0312:
            return False
        wp = int(msg.wParam)
        return wp in (SCRCPY_HOTKEY_ID, SCRCPY_HOTKEY_ID2)
    except Exception:
        return False

"""Lightweight tests for ADB serial token parsing."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from devicedeck.ui.tabs.file_explorer_tab import _first_serial_token


def test_empty_and_whitespace():
    assert _first_serial_token("") == ""
    assert _first_serial_token("   ") == ""
    assert _first_serial_token(None) == ""


def test_serial():
    assert _first_serial_token("ABC12345 device usb") == "ABC12345"
    assert _first_serial_token("RFCY12345") == "RFCY12345"

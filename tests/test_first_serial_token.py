from adbnik.ui.tabs.file_explorer_tab import _first_serial_token


def test_first_serial_token_basic() -> None:
    assert _first_serial_token("COM7") == "COM7"
    assert _first_serial_token("  com3 ") == "com3"

"""ANSI → HTML converter tests."""

from adbnik.ui.ansi_html import AnsiToHtmlConverter, preprocess_escape_noise, preprocess_pty_stream


def test_sgr_green():
    c = AnsiToHtmlConverter()
    html, plain = c.feed("\x1b[32mOK\x1b[0m")
    assert plain == "OK"
    assert "4caf50" in html or "green" in html.lower() or "#4caf50" in html


def test_percent_bracket_esc_alias():
    c = AnsiToHtmlConverter()
    s = preprocess_pty_stream("%[0;32mINFO%[0m")
    html, plain = c.feed(s)
    assert plain == "INFO"
    assert "INFO" in html


def test_esc_split_across_newlines_merged():
    """Embedded logs often split ESC and CSI across lines; merge before ANSI parse."""
    c = AnsiToHtmlConverter()
    s = preprocess_escape_noise("C2: 1.2.3 \x1b\n[1;36mSYS: hello\n")
    assert "\x1b\n[" not in s
    html, plain = c.feed(s)
    assert "[1;36m" not in plain
    assert "SYS: hello" in plain

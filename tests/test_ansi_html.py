"""ANSI → HTML converter tests."""

from adbnik.ui.ansi_html import (
    AnsiToHtmlConverter,
    emulate_terminal_carriage_return,
    preprocess_escape_noise,
    preprocess_pty_stream,
    preprocess_serial_stream,
    strip_ansi_for_display,
)


def test_emulate_cr_overwrite_not_glue():
    assert emulate_terminal_carriage_return("ls\rbin") == "bin"
    assert emulate_terminal_carriage_return("a\r\nb") == "a\nb"
    assert emulate_terminal_carriage_return("hello\rworld") == "world"


def test_embedded_terminal_ignores_background_colors():
    """Full-pane ANSI background (e.g. slog2info) must not repaint the QTextEdit surface."""
    c = AnsiToHtmlConverter(ignore_background=True)
    html, _plain = c.feed("\x1b[44m\x1b[30mX\x1b[0m")
    assert "background" not in html.lower()


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


def test_orphan_reset_line_stripped():
    """UART/SSH sometimes leave [0;39m on its own line when ESC is lost."""
    s = preprocess_escape_noise("ok\n[0;39m\nnext\n")
    assert "[0;39m" not in s
    assert "ok" in s
    assert "next" in s


def test_lone_esc_byte_stripped():
    """Bare 0x1b (Qt may show as 'ESC') should be removed when not starting CSI/OSC."""
    s = preprocess_escape_noise("ok\x1b\nmore")
    assert "\x1b" not in s
    assert "ok" in s and "more" in s


def test_serial_preprocess_removes_survivor_esc():
    """Serial pipeline must not leave U+001B for QTextEdit to paint as 'ESC'."""
    s = preprocess_serial_stream("line\x1b\x1bmore")
    assert "\x1b" not in s


def test_serial_preprocess_strips_bracket_39m():
    s = preprocess_serial_stream("line\n[39m\n")
    assert "[39m" not in s


def test_serial_preprocess_strips_corrupt_0_dot_39m():
    """UART may show ``[0.39m`` when ``[0;39m`` loses semicolon / ESC."""
    s = preprocess_serial_stream("ok\n[0.39m\n")
    assert "[0.39m" not in s


def test_strip_ansi_for_display_removes_sequences_and_orphan_0_39m():
    s = strip_ansi_for_display("a\x1b[32mok\x1b[0m\n0;39m\n[0;39m")
    assert "\x1b" not in s
    assert "0;39m" not in s
    assert "ok" in s

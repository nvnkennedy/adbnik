"""ANSI → HTML converter tests."""

from adbnik.ui.ansi_html import (
    AnsiToHtmlConverter,
    ensure_remote_pty_visual_line_breaks,
    get_prompt_palette,
    inject_shell_prompt_gaps,
    normalize_remote_pty_plain_text,
    preprocess_escape_noise,
    preprocess_prompt_lines_for_highlight,
    preprocess_pty_stream,
    preprocess_serial_stream,
    strip_ansi_for_display,
    strip_sgr_sequences_for_prompt,
    style_prompt_line_html,
)


def test_normalize_remote_pty_plain_text_maps_cr():
    assert normalize_remote_pty_plain_text("ls\rbin") == "ls\nbin"
    assert normalize_remote_pty_plain_text("a\r\nb") == "a\nb"
    assert normalize_remote_pty_plain_text("\n" * 10) == "\n" * 7


def test_normalize_remote_pty_strips_cr_after_shell_prompt():
    """Lone CR after $/#/ > is same-line redraw; must not split ``#`` and ``ls`` (SSH/ADB)."""
    assert normalize_remote_pty_plain_text("root@h:~# \rls") == "root@h:~# ls"
    assert normalize_remote_pty_plain_text("x $ \rfoo") == "x $ foo"


def test_ensure_remote_pty_visual_line_breaks_prompt_after_output():
    tail = "acct bin vendor_dlkm"
    chunk = "i3_max_civic_vendor_star3_5:/ $ "
    out = ensure_remote_pty_visual_line_breaks(tail, chunk)
    assert out.startswith("\n") and "i3_max" in out


def test_ensure_remote_pty_visual_line_breaks_ssh_prompt():
    tail = "some output"
    chunk = "root@169.254.17.90:~# "
    assert ensure_remote_pty_visual_line_breaks(tail, chunk).startswith("\n")


def test_ensure_remote_pty_visual_line_breaks_after_echoed_command():
    tail = "root@host:~# ls"
    chunk = "bin\ndata\n"
    assert ensure_remote_pty_visual_line_breaks(tail, chunk).startswith("\n")


def test_ensure_remote_pty_visual_line_breaks_noop_when_tail_has_newline():
    assert ensure_remote_pty_visual_line_breaks("ok\n", "bin") == "bin"


def test_ensure_remote_pty_no_double_lead_when_chunk_starts_with_newline():
    tail = "out"  # no trailing newline; would normally consider glue
    chunk = "\nroot@h:~# "
    assert not ensure_remote_pty_visual_line_breaks(tail, chunk).startswith("\n\n")


def test_style_prompt_line_unix_ssh():
    loc = get_prompt_palette("local")
    h = style_prompt_line_html("user@host:~$ ")
    assert h and loc.user in h and "$" in h and "user" in h


def test_style_prompt_line_adb_device_path():
    """ADB/Android shell: hostname:/path $ tail — no user@."""
    adb = get_prompt_palette("adb")
    h = style_prompt_line_html("vivo:/ $ ", palette=adb)
    assert h and "vivo" in h and "/" in h and "$" in h and adb.user in h


def test_style_prompt_line_adb_same_line_command():
    adb = get_prompt_palette("adb")
    h = style_prompt_line_html("vivo:/system/bin $ ls -la", palette=adb)
    assert h and "vivo" in h and "ls" in h and adb.typed_input in h


def test_inject_shell_prompt_gaps_glued_adb():
    assert inject_shell_prompt_gaps("vivo_25:/$ls") == "vivo_25:/$ ls"
    assert inject_shell_prompt_gaps("root@h:/data#id") == "root@h:/data# id"


def test_preprocess_prompt_injects_gap():
    out = preprocess_prompt_lines_for_highlight("vivo:/$ls\n", palette_kind="adb")
    assert "$ ls" in out


def test_style_prompt_ssh_minimal_hash_green():
    ssh = get_prompt_palette("ssh")
    h = style_prompt_line_html("# reboot", palette=ssh)
    assert h and ssh.sig_hash and ssh.sig_hash in h


def test_style_prompt_ssh_host_then_hash():
    ssh = get_prompt_palette("ssh")
    h = style_prompt_line_html("bmw_unit # ls", palette=ssh)
    assert h and "bmw_unit" in h and ssh.sig_hash in h


def test_style_prompt_line_powershell():
    h = style_prompt_line_html(r"PS C:\Windows\System32>")
    assert h and "PS" in h and "System32" in h


def test_prompt_highlight_feed_unix():
    pal = get_prompt_palette("ssh")
    c = AnsiToHtmlConverter(prompt_highlight=True, prompt_palette=pal)
    html, plain = c.feed("root@box:/tmp$ ")
    assert plain.strip()
    assert pal.sig in html


def test_prompt_line_with_leading_sgr():
    """Reset / SGR must not block prompt coloring."""
    loc = get_prompt_palette("local")
    line = "\x1b[0muser@host:~$ ls"
    h = style_prompt_line_html(line, strip_sgr_sequences_for_prompt(line))
    assert h and "ls" in h and loc.user in h


def test_prompt_unix_same_line_command():
    h = style_prompt_line_html("user@host:/data $ chmod +x a.sh")
    assert h and "chmod" in h and "$" in h


def test_plain_output_line_uses_output_tint():
    """Non-prompt lines with default SGR get a muted output color vs prompt input."""
    c = AnsiToHtmlConverter(prompt_highlight=True)
    html, plain = c.feed("hello world\n")
    assert "hello world" in plain
    assert get_prompt_palette("local").line_output in html


def test_preprocess_prompt_lines_strips_sgr_on_detected_prompt():
    """Colored SSH prompts become plain so HTML prompt styling applies."""
    line = "\x1b[32muser@host:~$\x1b[0m ls"
    out = preprocess_prompt_lines_for_highlight(line + "\n", palette_kind="ssh")
    assert "\x1b" not in out
    assert "user@host" in out


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


def test_serial_preprocess_strips_bare_0_39m_line():
    s = preprocess_serial_stream("a\n0;39m\nb\n")
    assert "0;39m" not in s
    assert "a" in s and "b" in s


def test_serial_preprocess_strips_lonely_bracket_039():
    s = preprocess_serial_stream("ok\n[0;39m\nmore")
    assert "[0;39m" not in s
    assert "ok" in s and "more" in s


def test_strip_ansi_for_display_removes_sequences_and_orphan_0_39m():
    s = strip_ansi_for_display("a\x1b[32mok\x1b[0m\n0;39m\n[0;39m")
    assert "\x1b" not in s
    assert "0;39m" not in s
    assert "ok" in s


def test_strip_ansi_erase_line_not_glue_ls_bin():
    """EL between echoed token and following text must not become ``lsbin`` when CSI is stripped."""
    s = strip_ansi_for_display("ls\x1b[Kbin")
    assert "lsbin" not in s
    assert "ls" in s and "bin" in s


def test_strip_ansi_cursor_forward_not_glue_ls_bin():
    """CUF (cursor forward) is common in columnar listings; stripping bare caused ``lsbin``."""
    s = strip_ansi_for_display("ls\x1b[20Cbin")
    assert "lsbin" not in s
    assert "ls" in s and "bin" in s

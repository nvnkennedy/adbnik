"""Convert terminal streams with ANSI SGR codes into HTML for QTextEdit; also yield plain text for logs."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern, Tuple

# xterm 6×6×6 color cube + grayscale (standard mapping)
_CUBE = [0, 95, 135, 175, 215, 255]


def _256_to_rgb(n: int) -> str:
    n = int(n) & 255
    if n < 16:
        base = [
            "#000000",
            "#cd3131",
            "#0dbc79",
            "#e5e510",
            "#2472c8",
            "#bc3fbc",
            "#11a8cd",
            "#e5e5e5",
            "#666666",
            "#f14c4c",
            "#23d18b",
            "#f5f543",
            "#3b8eea",
            "#d670d6",
            "#29b8db",
            "#ffffff",
        ]
        return base[n] if n < len(base) else "#e0e0e0"
    if n < 232:
        n -= 16
        r = _CUBE[(n // 36) % 6]
        g = _CUBE[(n // 6) % 6]
        b = _CUBE[n % 6]
        return f"#{r:02x}{g:02x}{b:02x}"
    gscale = 8 + (n - 232) * 10
    return f"#{gscale:02x}{gscale:02x}{gscale:02x}"


_ANSI_FG = {
    30: "#000000",
    31: "#f44336",
    32: "#4caf50",
    33: "#ffeb3b",
    34: "#2196f3",
    35: "#e91e63",
    36: "#00bcd4",
    37: "#e0e0e0",
    90: "#666666",
    91: "#ff5252",
    92: "#69f0ae",
    93: "#fff59d",
    94: "#64b5f6",
    95: "#ea80fc",
    96: "#84ffff",
    97: "#ffffff",
}
_ANSI_BG = {
    40: "#000000",
    41: "#b71c1c",
    42: "#1b5e20",
    43: "#f9a825",
    44: "#0d47a1",
    45: "#880e4f",
    46: "#006064",
    47: "#e0e0e0",
    100: "#444444",
    101: "#c62828",
    102: "#2e7d32",
    103: "#fbc02d",
    104: "#1565c0",
    105: "#6a1b9a",
    106: "#00838f",
    107: "#f5f5f5",
}

_DEFAULT_FG = "#f0f3f6"


@dataclass(frozen=True)
class PromptPalette:
    """Per-session prompt segmentation + default plain-line output tint (when SGR is default)."""

    user: str
    sep: str
    host: str
    path: str
    sig: str
    ps_prefix: str
    prompt_input: str
    line_output: str
    # Optional color for ``#`` when it should differ from ``$`` (e.g. SSH root hash prompt).
    sig_hash: Optional[str] = None


def get_prompt_palette(kind: str) -> PromptPalette:
    """``kind``: ssh | adb | powershell | cmd | serial | local"""
    return _PROMPT_PALETTES.get(kind, _PROMPT_PALETTES["local"])


_PROMPT_PALETTES: Dict[str, PromptPalette] = {
    # SSH: prompt segments vs typed tail vs command output (high contrast)
    "ssh": PromptPalette(
        user="#38bdf8",
        sep="#64748b",
        host="#22d3ee",
        path="#4ade80",
        sig="#fb923c",
        ps_prefix="#c4b5fd",
        prompt_input="#fef08a",
        line_output="#94a3b8",
        sig_hash="#22c55e",
    ),
    # ADB: device vs path vs marker vs input vs listing output
    "adb": PromptPalette(
        user="#2dd4bf",
        sep="#64748b",
        host="#5eead4",
        path="#e2e8f0",
        sig="#fb923c",
        ps_prefix="#ddd6fe",
        prompt_input="#fde047",
        line_output="#a1a1aa",
    ),
    "powershell": PromptPalette(
        user="#a78bfa",
        sep="#94a3b8",
        host="#c4b5fd",
        path="#7dd3fc",
        sig="#f472b6",
        ps_prefix="#e9d5ff",
        prompt_input="#fca5a5",
        line_output="#b4c6d6",
    ),
    "cmd": PromptPalette(
        user="#38bdf8",
        sep="#8b949e",
        host="#94a3b8",
        path="#93c5fd",
        sig="#facc15",
        ps_prefix="#d8b4fe",
        prompt_input="#fde047",
        line_output="#b8c4ce",
    ),
    "serial": PromptPalette(
        user="#fbbf24",
        sep="#a8a29e",
        host="#fcd34d",
        path="#fde047",
        sig="#f87171",
        ps_prefix="#e879f9",
        prompt_input="#fdba74",
        line_output="#a8a29e",
    ),
    "local": PromptPalette(
        user="#79c0ff",
        sep="#8b949e",
        host="#a5d6ff",
        path="#7ee787",
        sig="#ff7b72",
        ps_prefix="#d2a8ff",
        prompt_input="#f0ab68",
        line_output="#b8c4ce",
    ),
}


# When the PTY has not set SGR color (default fg), tint whole lines by keywords — Moba-style log reading.
_SEMANTIC_LINE_PATTERNS: List[Tuple[Pattern[str], str]] = [
    (re.compile(r"(?i).*\b(ERROR|FATAL|CRITICAL)\b.*"), "#ff5252"),
    (re.compile(r"(?i).*\b(EXCEPTION)\b.*"), "#ef5350"),
    (re.compile(r"(?i).*\b(FAIL|FAILED|FAILURE)\b.*"), "#ff7043"),
    (re.compile(r"(?i).*\b(WARN|WARNING)\b.*"), "#ffc107"),
    (re.compile(r"(?i).*\b(DEBUG|TRACE)\b.*"), "#78909c"),
    (re.compile(r"(?i).*\b(INFO|NOTICE)\b.*"), "#66bb6a"),
    (re.compile(r"(?i).*\b(SUCCESS|PASSED)\b.*"), "#4caf50"),
    (re.compile(r"(?i).*(timed out|connection refused|connection reset|no route to host|network is unreachable).*"), "#ff5252"),
]


def _semantic_fg_for_plain_line(line: str) -> Optional[str]:
    if not (line or "").strip():
        return None
    for pat, col in _SEMANTIC_LINE_PATTERNS:
        if pat.search(line):
            return col
    return None


def _split_params(s: str) -> List[int]:
    if not s.strip():
        return [0]
    out: List[int] = []
    for part in s.split(";"):
        part = part.strip()
        if not part:
            out.append(0)
        else:
            try:
                out.append(int(part))
            except ValueError:
                out.append(0)
    return out


@dataclass
class _SgrState:
    fg: str = _DEFAULT_FG
    bg: Optional[str] = None
    bold: bool = False

    def reset(self) -> None:
        self.fg = _DEFAULT_FG
        self.bg = None
        self.bold = False

    def css(self) -> str:
        parts = [f"color:{self.fg}"]
        if self.bg:
            parts.append(f"background-color:{self.bg}")
        if self.bold:
            parts.append("font-weight:600")
        return ";".join(parts) + ";"


def preprocess_pty_stream(data: str) -> str:
    """Normalize line endings; fix dropped ESC before CSI (%[); drop NUL/BEL; keep TAB/newline."""
    if not data:
        return data
    # CRLF only — lone CR is normalized later in normalize_remote_pty_plain_text() for the terminal view.
    data = data.replace("\r\n", "\n")
    # UART / tooling sometimes drops ESC (0x1b) so CSI shows as %[ …
    data = re.sub(r"(?<!\x1b)%\[", "\x1b[", data)
    # Saved logs / some terminals show ESC as two chars ^[ — restore real ESC for SGR
    data = re.sub(r"\^\[", "\x1b[", data)
    # OSC hyperlinks / titles — strip (QTextEdit won't interpret)
    data = re.sub(r"\x1b\][^\x07]*(\x07|\x1b\\)", "", data)
    data = re.sub(r"[\x00\x07]", "", data)
    data = re.sub(r"[\x0b\x0c\x0e-\x1a]", "", data)
    # Collapse "reset-only" lines (common embedded log pattern) that double-space the view
    data = re.sub(r"\n(?:\s*\x1b\[[0-9;]*m)+\s*\n", "\n", data)
    # Drop lone SGR resets immediately before a newline (line discipline quirk on some UARTs)
    data = re.sub(r"\x1b\[[0-9;]*m(?=\r?\n)", "", data)
    # Remove lines that contain only whitespace and ANSI SGR sequences (common in embedded logs)
    data = re.sub(r"(?m)^(?:\s|\x1b\[[0-9;]*m)+\s*$", "", data)
    # Merge runs of blank lines after stripping
    data = re.sub(r"\n{2,}", "\n", data)
    return data


def normalize_remote_pty_plain_text(text: str) -> str:
    """
    Map PTY carriage returns for SSH/ADB plain-text rendering only (not used for serial UART).

    QTextEdit cannot emulate TTY ``\\r`` (return to column 0). ``\\r\\n`` is one newline. Lone
    ``\\r`` after a shell prompt token (``$``, ``#``, ``>``) is usually a same-line redraw (bash /
    Android shell) — stripping it avoids splitting ``#`` and ``ls`` onto separate rows. Other lone
    ``\\r`` still become ``\\n`` so listings stay readable (see tests). Long runs of blank lines
    are capped.
    """
    if not text:
        return text
    text = text.replace("\r\n", "\n")
    # Same-line redraw after prompt: replace ``\s*\\r`` with one space so "# \\rls" becomes "# ls" (not "#ls").
    text = re.sub(r"(?<=[\$#>])\s*\r+(?!\n)", " ", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{8,}", "\n\n\n\n\n\n\n", text)
    return text


# SSH / Android adb shell: next chunk may start with a prompt while the scrollback tail has no ``\n``
# (PTY often omits a line break between the last column of ``ls`` and the next prompt).
_REMOTE_CHUNK_STARTS_WITH_PROMPT = re.compile(
    r"^\s*(?:\d+\|)?"
    r"(?:"
    r"[\w.-]+@[^:\s]+:[^\n]*?[$#>]\s*"  # user@host:path# or $ (with or without space before #/$)
    r"|"
    r"[\w][\w.+-]*:\/\s*\$\s*"  # Android …:/ $
    r"|"
    r"[\w][\w.+-]*:\/\S*\s*#\s*"  # Android …:/path#
    r")"
)

# Last line is ``…# ls`` / ``…$ mount`` style: prompt plus echoed command, but no newline before output.
_TAIL_ENDS_WITH_PROMPT_AND_ECHOED_CMD = re.compile(r"(?:^|\n)[^\n]*[$#>]\s+\S+[^\n]*$")


def ensure_remote_pty_visual_line_breaks(tail_before_chunk: str, chunk: str) -> str:
    """
    Insert a leading newline when the PTY glued two logical lines into one QTextEdit line.

    Used only for SSH/ADB plain-text streaming. Safe to no-op when ``tail_before_chunk`` already
    ends with ``\\n``. If ``chunk`` already begins with line breaks, do not prepend another (avoids
    stacked blank rows after output).
    """
    if not chunk:
        return chunk
    if tail_before_chunk.endswith("\n"):
        return chunk
    rest = chunk.lstrip("\n")
    if not rest:
        return chunk
    # Chunk already starts with newline(s): separation exists — extra prepend would double-space.
    if chunk.startswith("\n"):
        return chunk
    first_line = rest.split("\n", 1)[0]
    if _REMOTE_CHUNK_STARTS_WITH_PROMPT.match(first_line):
        return "\n" + chunk
    if _TAIL_ENDS_WITH_PROMPT_AND_ECHOED_CMD.search(tail_before_chunk):
        return "\n" + chunk
    return chunk


def preprocess_escape_noise(data: str) -> str:
    """Fix ESC/CSI split across newlines and orphan escape lines (SSH, serial, embedded Linux logs)."""
    data = preprocess_pty_stream(data)
    if not data:
        return data
    # Whitespace between ESC and '[' (some stacks insert a space)
    data = re.sub(r"\x1b\s+\[", "\x1b[", data)
    # ESC and '[' were split by CR/LF (common with conhost / UART / line discipline)
    data = re.sub(r"\x1b\s*\r?\n\s*\[", "\x1b[", data)
    # Line contains only ESC (often rendered as a lone “ESC” glyph / blank line)
    data = re.sub(r"(?m)^\s*\x1b\s*$", "", data)
    # Line is only a CSI SGR body like [1;36m (ESC was on the previous line)
    data = re.sub(r"(?m)^\s*\[(?:\d{1,4};)*\d{1,4}m\s*$", "", data)
    # Orphan reset lines: [0;39m], [39m], [0m] when ESC was dropped or split across lines
    data = re.sub(r"(?m)^\s*\[(?:0;)?39m\s*$", "", data)
    data = re.sub(r"(?m)^\s*\[0m\s*$", "", data)
    # Whole line is only bare ``0;39m`` / ``0.39m`` (UART split CSI)
    data = re.sub(r"(?m)^\s*0;39m\s*$", "", data)
    data = re.sub(r"(?m)^\s*0\.39m\s*$", "", data, flags=re.I)
    # CSI SGR without leading ESC (UART / logging dropped 0x1b) — strip anywhere
    data = re.sub(r"(?<!\x1b)\[(?:\d{1,4};)*\d{1,4}m", "", data)
    data = re.sub(r"(?<!\x1b)\[(?:0;)?39m", "", data)
    data = re.sub(r"(?<!\x1b)\[0m\b", "", data)
    # New line that is only bracket noise left after a newline-split CSI
    data = re.sub(r"(?m)^\s*\[\s*$", "", data)
    # Qt may paint bare 0x1b as a visible "ESC" glyph; drop lone ESC not starting CSI (\x1b[) or OSC (\x1b]).
    data = re.sub(r"\x1b(?![\[\]])", "", data)
    data = re.sub(r"\n{2,}", "\n", data)
    return data


def preprocess_serial_esc_boundaries(data: str) -> str:
    """Remove UART/miniterm ESC bytes that sit on their own row/column (Qt may paint them as visible ESC)."""
    if not data:
        return data
    data = re.sub(r"\r\n\x1b(?!\[)", "\r\n", data)
    data = re.sub(r"\n\x1b(?=\r?\n)", "\n", data)
    data = re.sub(r"\n\x1b\n", "\n", data)
    data = re.sub(r"(?m)^\x1b+(?=\r?\n)", "", data)
    return data


def preprocess_serial_stream(data: str) -> str:
    """UART / miniterm: strip reset spam and CSI fragments when ESC is dropped or echoed oddly."""
    if not data:
        return data
    data = data.replace("\r\n", "\n").replace("\r", "\n")
    data = data.replace("\x07", "")
    data = preprocess_escape_noise(data)
    if not data:
        return data
    # Do not strip ``\x1b`` before ``]`` here — that would break OSC removal below (preprocess_escape_noise
    # already removed bare ESCs not starting CSI/OSC).
    # Drop full CSI sequences (SGR colors like \x1b[32m, cursor moves, etc.) — serial is plain log text.
    data = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", data)
    # Second pass: UART sometimes splits CSI so the first pass leaves a remainder.
    data = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", data)
    # OSC (title/hyperlink) without ST — strip greedy safe tail
    data = re.sub(r"\x1b\][^\x07\x1b]{0,4096}(?:\x07|\x1b\\)", "", data)
    # Full reset sequences anywhere (not only before newline)
    data = re.sub(r"\x1b\[(?:0;)?39m", "", data)
    data = re.sub(r"\x1b\[0m", "", data)
    # UART sometimes drops ESC so "[0;39m" / "[39m" appears as plain text
    data = re.sub(r"(?<!\x1b)\[(?:0;)?39m", "", data)
    data = re.sub(r"(?<!\x1b)\[0\.39m", "", data)
    data = re.sub(r"(?<!\x1b)\[39m", "", data)
    data = re.sub(r"(?<!\x1b)\[0m\b", "", data)
    # Bare fragments without ``[`` (split UART / corrupted CSI)
    data = re.sub(r"(?<![\[\x1b])0\.39m", "", data, flags=re.I)
    data = re.sub(r"(?<![\[\x1b])0;39m", "", data)
    # Lines that contain only SGR noise
    data = re.sub(
        r"(?m)^(?:\s|\x1b\[[0-9;]*m|\[(?:0;)?39m|\[39m|\[0m|0;39m|0\.39m)+\s*$",
        "",
        data,
        flags=re.I,
    )
    # Newline sandwiched between resets (still doubles vertical space)
    data = re.sub(r"\n(?:\s*\x1b\[[0-9;]*m)+\s*\n", "\n", data)
    data = re.sub(r"\n{2,}", "\n", data)
    # Last resort: QTextEdit can still paint U+001B as a visible "ESC" — remove any survivors.
    data = data.replace("\x1b", "").replace("\u009b", "").replace("\u241b", "")
    # Orphan ``0;39m`` / ``0.39m`` without ``[`` (UART bit errors)
    data = data.replace("0;39m", "").replace("[0;39m", "")
    data = re.sub(r"(?<![\[\x1b])0\.39m", "", data, flags=re.I)
    # Lines that are only corrupted reset tokens (optional brackets / semicolon variants)
    data = re.sub(r"(?m)^\s*\[?0[;.]39m\]?\s*$", "", data, flags=re.I)
    data = re.sub(r"(?m)^\s*0[;.]39m\s*$", "", data, flags=re.I)
    # Occasional UART fragments: full bracket reset appearing alone after ESC was stripped.
    data = re.sub(r"(?m)^\s*\[0;39m\s*$", "", data)
    data = re.sub(r"\[0;39m", "", data)
    return data


def strip_ansi_for_log(text: str) -> str:
    """Plain text for session log files."""
    if not text:
        return text
    text = preprocess_pty_stream(text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return text


# Fast strip for SSH/ADB terminal *display*: QTextCursor.insertText is orders of magnitude
# cheaper than insertHtml; use this after preprocess_escape_noise on the UI thread.
_OSC_STRIP_FAST = re.compile(r"\x1b\][^\x07\x1b]{0,8192}(?:\x07|\x1b\\)")


def strip_ansi_for_display(text: str) -> str:
    """Remove ANSI/OSC for plain terminal view (high-throughput SSH/ADB). Keeps UI responsive."""
    if not text:
        return text
    # SGR (colors / ``0m`` reset): strip entirely.
    text = re.sub(r"\x1b\[[0-?]*[ -/]*m", "", text)
    # Every other CSI (cursor moves, EL/ED, modes, etc.): one space. Removing them bare collapses
    # layout the TTY applied with cursor motion (``ls`` + CUF + ``bin`` → ``lsbin`` after first line).
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", " ", text)
    text = _OSC_STRIP_FAST.sub("", text)
    text = re.sub(r"(?<!\x1b)\[(?:0;)?39m", "", text)
    text = re.sub(r"(?<!\x1b)\[0\.39m", "", text)
    text = text.replace("0;39m", "").replace("[0;39m", "")
    text = re.sub(r"(?<![\[\x1b])0\.39m", "", text, flags=re.I)
    text = re.sub(r"(?<![\[\x1b])0;39m", "", text)
    text = text.replace("\x1b", "").replace("\u009b", "")
    return text


_CSI_ANY = re.compile(r"\x1b\[[\x30-\x3f\x20-\x2f]*[\x40-\x7e]")


def _csi_is_complete(tail: str) -> bool:
    if not tail or tail[0] != "\x1b":
        return True
    if len(tail) == 1:
        return False
    if tail[1] != "[":
        return True
    if len(tail) < 3:
        return False
    for j in range(2, len(tail)):
        c = tail[j]
        if "\x40" <= c <= "\x7e":
            return True
    return False


def _carry_incomplete_esc(s: str) -> Tuple[str, str]:
    """Split into (complete, carry) when the end of s is an incomplete ESC/CSI sequence."""
    if not s:
        return "", ""
    last = s.rfind("\x1b")
    if last < 0:
        return s, ""
    tail = s[last:]
    if _csi_is_complete(tail):
        return s, ""
    return s[:last], tail


def _prompt_marker_css(pal: PromptPalette, ch: str) -> str:
    """Color for ``$`` vs ``#`` prompt markers (SSH may use a distinct green for ``#``)."""
    if ch == "#" and pal.sig_hash is not None:
        return pal.sig_hash
    return pal.sig


def strip_sgr_sequences_for_prompt(line: str) -> str:
    """Strip CSI sequences so prompt regexes match (SGR, cursor moves, EL/ED, etc.)."""
    if not line:
        return line
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)


def style_prompt_line_html(
    line: str,
    bare: Optional[str] = None,
    *,
    palette: Optional[PromptPalette] = None,
) -> Optional[str]:
    """Return colored HTML for one logical prompt line (Unix/CMD/PowerShell), or None to use default span.

    ``bare`` should be the same line with SGR stripped; if omitted it is derived from ``line``.
    Includes optional text **after** ``#`` / ``$`` / ``>`` (typed command on the same line).
    """
    pal = palette or get_prompt_palette("local")
    if not (line or "").strip():
        return None
    s = (bare if bare is not None else strip_sgr_sequences_for_prompt(line)).rstrip("\r")

    def _tail_span(rest: str) -> str:
        if not rest:
            return ""
        return f'<span style="color:{pal.prompt_input}">{html.escape(rest)}</span>'

    # PowerShell: PS C:\path>  optional tail
    m = re.match(r"^(PS\s+)(.+)(>+)(.*)$", s)
    if m:
        prefix, mid, gt, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        return (
            f'<span style="color:{pal.ps_prefix}">{html.escape(prefix)}</span>'
            f'<span style="color:{pal.path}">{html.escape(mid)}</span>'
            f'<span style="color:{pal.sig}">{html.escape(gt)}</span>'
            f"{_tail_span(tail)}"
        )

    # CMD: C:\...> optional tail
    m = re.match(r"^([A-Za-z]:[^>\r\n]*)(>)(.*)$", s)
    if m:
        path, gt, tail = m.group(1), m.group(2), m.group(3)
        return (
            f'<span style="color:{pal.path}">{html.escape(path)}</span>'
            f'<span style="color:{pal.sig}">{html.escape(gt)}</span>'
            f"{_tail_span(tail)}"
        )

    t = s.strip()
    # Bare ``#`` / ``# ls`` (busybox / embedded), no user@host on the line
    if t.startswith("#") and "@" not in t:
        m0 = re.match(r"^#(\s*)(.*)$", t)
        if m0:
            sp, rest = m0.group(1), m0.group(2)
            col = _prompt_marker_css(pal, "#")
            return f'<span style="color:{col}">#</span>{_tail_span(sp + rest)}'
    # ``device # cmd`` / ``host $ cmd`` without ``user@`` or ``host:/path`` (e.g. ``bmw_new_device #``)
    m1 = re.match(r"^(\S+)\s+([$#])(.*)$", t)
    if m1 and "@" not in m1.group(1) and ":" not in m1.group(1):
        dev, sigc, tail = m1.group(1), m1.group(2), m1.group(3)
        mc = _prompt_marker_css(pal, sigc)
        return (
            f'<span style="color:{pal.user}">{html.escape(dev)}</span>'
            f'<span style="color:{pal.sep}"> </span>'
            f'<span style="color:{mc}">{html.escape(sigc)}</span>'
            f"{_tail_span(tail)}"
        )

    # Unix-style / ADB: user@host:path … # or $ … optional tail (pick rightmost # or $ that yields user@host:path)
    t2 = s.rstrip()
    cand = [(t2.rfind("#"), "#"), (t2.rfind("$"), "$")]
    cand = [(j, ch) for j, ch in cand if j >= 0]
    cand.sort(key=lambda x: x[0], reverse=True)
    for j, sig_ch in cand:
        head = t2[:j].rstrip()
        tail = t2[j + 1 :]
        # ADB / embedded shell: hostname:/path #|$ tail (no user@), e.g. vivo:/ $
        if "@" not in head:
            colon = head.find(":")
            if colon > 0:
                dev = head[:colon]
                rest_path = head[colon + 1 :]
                if dev.strip():
                    mc = _prompt_marker_css(pal, sig_ch)
                    return (
                        f'<span style="color:{pal.user}">{html.escape(dev)}</span>'
                        f'<span style="color:{pal.sep}">:</span>'
                        f'<span style="color:{pal.path}">{html.escape(rest_path)}</span>'
                        f'<span style="color:{mc}">{html.escape(sig_ch)}</span>'
                        f"{_tail_span(tail)}"
                    )
        at = head.find("@")
        if at <= 0:
            continue
        colon = head.find(":", at + 1)
        if colon <= at:
            continue
        user = head[:at]
        host = head[at + 1 : colon]
        path = head[colon + 1 :]
        mc = _prompt_marker_css(pal, sig_ch)
        return (
            f'<span style="color:{pal.user}">{html.escape(user)}</span>'
            f'<span style="color:{pal.sep}">@</span>'
            f'<span style="color:{pal.host}">{html.escape(host)}</span>'
            f'<span style="color:{pal.sep}">:</span>'
            f'<span style="color:{pal.path}">{html.escape(path)}</span>'
            f'<span style="color:{mc}">{html.escape(sig_ch)}</span>'
            f"{_tail_span(tail)}"
        )

    return None


def preprocess_prompt_lines_for_highlight(data: str, *, palette_kind: str = "local") -> str:
    """SSH/ADB: strip in-band SGR on lines that match a shell prompt so prompt HTML styling applies."""
    if not data:
        return data
    lines = data.split("\n")
    pal = get_prompt_palette(palette_kind)
    out: List[str] = []
    for line in lines:
        bare = strip_sgr_sequences_for_prompt(line)
        if style_prompt_line_html(line, bare, palette=pal) is not None:
            out.append(bare)
        else:
            out.append(line)
    return "\n".join(out)


class AnsiToHtmlConverter:
    """Incremental ANSI → HTML (for QTextEdit) + parallel plain text (for prompts / logs)."""

    def __init__(
        self,
        *,
        ignore_background: bool = True,
        lift_black_foreground: bool = True,
        prompt_highlight: bool = True,
        prompt_palette: Optional[PromptPalette] = None,
        reset_fg_each_physical_line: bool = False,
    ) -> None:
        """Embedded terminal: ignore ANSI background (avoids full-pane blue/green from slog2info).
        ``lift_black_foreground`` maps SGR black (30) to a readable gray on dark UIs.
        ``reset_fg_each_physical_line``: before each new \\n-delimited row, reset SGR so SSH/ADB listings
        do not inherit the prompt line's ANSI color."""
        self._pending = ""
        self._state = _SgrState()
        self._ignore_background = bool(ignore_background)
        self._lift_black_foreground = bool(lift_black_foreground)
        self._prompt_highlight = bool(prompt_highlight)
        self._prompt_palette = prompt_palette or get_prompt_palette("local")
        self._reset_fg_each_physical_line = bool(reset_fg_each_physical_line)

    def reset(self) -> None:
        self._pending = ""
        self._state = _SgrState()

    def _apply_sgr(self, params: List[int]) -> None:
        i = 0
        while i < len(params):
            n = params[i]
            if n == 0:
                self._state.reset()
                i += 1
            elif n == 1:
                self._state.bold = True
                i += 1
            elif n == 22:
                self._state.bold = False
                i += 1
            elif 30 <= n <= 37:
                base = _ANSI_FG.get(n, _DEFAULT_FG)
                if self._lift_black_foreground and n == 30:
                    base = "#b8c0cc"
                self._state.fg = base
                i += 1
            elif 90 <= n <= 97:
                self._state.fg = _ANSI_FG.get(n, _DEFAULT_FG)
                i += 1
            elif n == 39:
                self._state.fg = _DEFAULT_FG
                i += 1
            elif 40 <= n <= 47:
                if not self._ignore_background:
                    self._state.bg = _ANSI_BG.get(n)
                i += 1
            elif 100 <= n <= 107:
                if not self._ignore_background:
                    self._state.bg = _ANSI_BG.get(n)
                i += 1
            elif n == 49:
                if not self._ignore_background:
                    self._state.bg = None
                i += 1
            elif n == 38 and i + 2 < len(params) and params[i + 1] == 5:
                self._state.fg = _256_to_rgb(params[i + 2])
                i += 3
            elif n == 48 and i + 2 < len(params) and params[i + 1] == 5:
                if not self._ignore_background:
                    self._state.bg = _256_to_rgb(params[i + 2])
                i += 3
            elif n == 38 and i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                r, g, b = params[i + 2], params[i + 3], params[i + 4]
                self._state.fg = f"#{r & 255:02x}{g & 255:02x}{b & 255:02x}"
                i += 5
            elif n == 48 and i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                if not self._ignore_background:
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    self._state.bg = f"#{r & 255:02x}{g & 255:02x}{b & 255:02x}"
                i += 5
            else:
                i += 1

    def _span_css(self, semantic_fg: Optional[str]) -> str:
        fg = semantic_fg if semantic_fg else self._state.fg
        parts = [f"color:{fg}"]
        if self._state.bg and not self._ignore_background:
            parts.append(f"background-color:{self._state.bg}")
        if self._state.bold:
            parts.append("font-weight:600")
        return ";".join(parts) + ";"

    def _emit_text(self, raw: str, html_parts: List[str], plain_parts: List[str]) -> None:
        if not raw:
            return
        plain_parts.append(raw)
        use_semantic = self._state.fg == _DEFAULT_FG and self._state.bg is None
        lines = raw.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                html_parts.append("<br/>")
                if self._reset_fg_each_physical_line:
                    self._state.reset()
            esc = html.escape(line)
            if not esc:
                continue
            if self._prompt_highlight:
                bare = strip_sgr_sequences_for_prompt(line)
                ph = style_prompt_line_html(line, bare, palette=self._prompt_palette)
                if ph:
                    html_parts.append(ph)
                    continue
            sem = _semantic_fg_for_plain_line(line) if use_semantic else None
            if sem is None and use_semantic:
                sem = self._prompt_palette.line_output
            html_parts.append(f'<span style="{self._span_css(sem)}">{esc}</span>')

    def feed(self, chunk: str) -> Tuple[str, str]:
        """Return (html_fragment, plain_text) for this chunk."""
        if not chunk:
            return "", ""
        data = self._pending + chunk
        self._pending = ""
        complete, inc = _carry_incomplete_esc(data)
        self._pending = inc

        html_parts: List[str] = []
        plain_parts: List[str] = []
        pos = 0
        for m in _CSI_ANY.finditer(complete):
            start, end = m.start(), m.end()
            if start > pos:
                self._emit_text(complete[pos:start], html_parts, plain_parts)
            seq = complete[start:end]
            if seq.endswith("m") and len(seq) >= 3:
                param_s = seq[2:-1]
                self._apply_sgr(_split_params(param_s))
            pos = end
        if pos < len(complete):
            self._emit_text(complete[pos:], html_parts, plain_parts)

        return "".join(html_parts), "".join(plain_parts)

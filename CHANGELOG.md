# Adbnik Changelog

All notable changes to this project are documented in this file.

The format loosely follows Keep a Changelog and Semantic Versioning.

## [2.5.6] - 2026-04-29

### Changed

- **Camera:** **OpenCV** (`opencv-python-headless`) is now a **direct dependency**. Preview runs on a **background thread** with frames capped ~960px wide; recording uses **OpenCV VideoWriter** for immediate finalize on stop (no long Qt Multimedia stall). Qt Multimedia remains fallback when OpenCV cannot enumerate devices.
- **Terminals:** **Prompt-line preprocessor** inserts a space after **`$`** / **`#`** when output glued commands (`vivo:/$ls` → `vivo:/$ ls`), plus **`>`** gaps for CMD/PowerShell-style glued tails — applies to **SSH, ADB, serial**, and **local** shells.
- **Terminals:** **Typed input** vs **command output**: distinct **`typed_input`** color vs **`line_output`** in ANSI HTML; **plain PTY stream** and **typing at prompt** use matching hex colors (`set_stream_plain_foreground` / `set_typing_foreground`).
- **Palettes:** Brighter **`prompt_input`**, **`line_output`**, and **`typed_input`** across ssh/adb/cmd/powershell/serial/local; default ANSI foreground slightly brighter.
- **Terminal widget:** Slightly brighter base text on dark preview pane.

### Fixed

- **Qt recording:** Faster finalize polling (**35ms** intervals; shorter sync wait when fallback needed).

## [2.5.5] - 2026-04-29

### Changed

- **Camera:** Video recording **finalizes after Stop** (wait for `QMediaRecorder` stopped state) so MP4 files are not truncated; leaving the tab or stopping the camera **sync-flushes** the recorder before unload.
- **Camera:** **Save-folder** flow unchanged; folder picker remains **Qt non-native** for responsiveness on Windows (see 2.5.4 file dialogs).
- **Camera:** Viewfinder picks the **largest resolution up to 1280px width** (fallback to max if none qualify) to reduce UI thread load; preview minimum size slightly reduced.
- **Camera:** After **photo** (`imageSaved`) or **video** save, an **Open file** choice matches other Save dialogs.

### Fixed

- **Camera:** First switch to the **Camera** tab stays on Camera after lazy init (**tab signals** blocked during placeholder swap).
- **Terminals:** **Local bash/zsh / Git Bash:** one visible space after **`$`** / **`#`** when the shell omits it (aligned with SSH/CMD/PowerShell behavior).

## [2.5.4] - 2026-04-29

### Changed

- **All terminals:** Stronger **typed input vs command output** colors (`prompt_input` brighter, `line_output` more muted) for SSH, ADB, PowerShell, CMD, serial, and local palettes; **per-line SGR reset** enabled for **CMD** and **PowerShell** like SSH/ADB.
- **Prompt caret gap:** One space after **`>`** for CMD (**including `C:>` paths**) and after **`PS …>`** for PowerShell.
- **Welcome banner:** **16px** title and **14px** meta lines, thicker **separator** rule after the block.
- **Application log:** Timestamp + message only — **removed** loud INFO/OK/ERR badge pills; message color still hints severity.
- **Camera:** **Pause-for-background** when leaving the tab (fast return + **Resume** via Start); **recording** stops cleanly on pause/stop/tab leave; **Record** disabled while preview paused; preview **fills** the tab stretch with **IgnoreAspectRatio** + max resolution; footer shortened.

### Fixed

- **CMD:** Synthetic prompt (`_maybe_append_synthetic_prompt`) is **called after output flushes**, so after **`ls`** / unknown-command errors the **`C:\…>`** line appears again with correct spacing regex **`[A-Za-z]:[^>\n]*>`**.
- **Light theme:** **Menu bar** menu titles use explicit **`#0f172a`** text (no invisible labels).

## [2.5.3] - 2026-04-29

### Changed

- **SSH prompts:** Root-style **`#`** uses a **green** marker (`sig_hash`); **`$`** stays distinct; **`device #`** lines (no `user@`, no `:/path`) match **ADB-style** segmentation.
- **Terminal:** Streaming HTML appends **preserve cursor and selection** when you are not at the document end (serial scrollback / copy while output runs).
- **Camera:** **KeepAspectRatio** + max viewfinder resolution for **sharper** frames; **rounded** `CameraChromeBtn` push buttons and dark preview chrome.
- **Log panel:** **Larger** type (app log **15px** content, **14px** in stylesheet; **Consolas 12** widget font).
- **Startup:** **`QApplication.setStyleSheet`** from config before **`MainWindow`**; theme apply is **synchronous** until the window is shown.

### Fixed

- **ADB / SSH:** Trailing space after **`$`/`#`** after **`rstrip`** (devices like **`vivo_25:/$`**).
- **Serial UART:** Remove lone **`[0;39m`** noise when ESC was dropped.
- **Light theme:** **`qt_msgbox_informativelabel`** contrast for paths on **Saved** dialogs.

## [2.5.2] - 2026-04-29

### Changed

- **Camera tab:** Loaded **only when you first open** the Camera tab so startup and other tabs stay responsive; preview **fills** the preview area, requests the **highest supported viewfinder resolution**, and uses **ignore aspect ratio** for scaling (sharper than small letterboxed scaling).
- **Open/save/folder dialogs:** `QFileDialog.getOpenFileName` / `getSaveFileName` / `getExistingDirectory` for **native Windows** styling where the platform supports it.
- **SSH / ADB terminals:** Prompt-line preprocessing uses the session palette (**ssh** / **adb**) so colored prompts strip correctly; **serial** chunks reset the ANSI parser state so incomplete escapes do not leak into the next chunk.

### Fixed

- **ADB / SSH:** Prompt palette applies per physical output line so **`ls`** listings are not stuck in the prompt color.
- **ADB / SSH:** One visible space after **`$`** / **`#`** when the shell omits it (caret alignment).
- **Serial UART:** Stronger scrub (**CR/BEL**, bracket CSI fragments) plus parser reset between chunks.
- **Light theme:** **`QMessageBox`** detail labels (`qt_msgbox_label`) and **Camera** lazy-load hint text use explicit contrast.
- **Regression:** Non-native Fusion file dialogs from 2.5.0 removed again in favor of native/static dialogs.

## [2.5.1] - 2026-04-29

### Fixed

- **Startup crash:** View → **Camera** menu used an undefined `st` variable (`NameError`). The Camera menu icon now uses `self.style()` like other View actions.

## [2.5.0] - 2026-04-29

### Added

- **Camera tab** (next to Screen Control): live preview (Qt Multimedia), **JPEG** snapshots, optional **MP4** recording, **Start / Stop / Pause / Restart**, save-folder picker; session persists while the app runs; **`camera_output_dir`** stored in config when you pick a folder.

### Changed

- **Terminal palettes:** Distinct **SSH** vs **ADB** vs **CMD** vs **PowerShell** vs **serial** colors for prompt segments, typed tail (**input**), and default-scrollback **output**; SSH/ADB streams normalize colored prompt lines so **prompt HTML** applies even when the shell wraps the prompt in **SGR**.
- **Welcome banner:** Uniform **13px** copy and a **full-width** separator rule (no short monospace rule).
- **Light theme dialogs:** **Fusion-style** open/save dialogs (`DontUseNativeDialog`) plus **`QFileDialog`** stylesheet rules fix invisible labels/text on Windows.

### Fixed

- **Serial UART:** Tighter collapse of **newline + ESC / `[0;39m` / `0;39m`** runs that added blank rows.

## [2.4.2] - 2026-04-29

### Added

- **Terminal prompts:** **ADB / device shell** prompts without `user@` (e.g. `vivo:/ $`) use the same segmented colors as SSH; text **after** `$` / `#` on that line uses a dedicated **input** tint; other plain lines use a muted **output** tint when ANSI is default.

### Fixed

- **Serial:** Stronger scrubbing of leaked **`[0;39m`** / **`0;39m`** / bracket-only CSI when **ESC** is lost, without dropping valid escape sequences that still start with **0x1b**.
- **Serial typing:** **Preserve** typed lines at the prompt when the UART link does not echo locally (input remains visible after Enter).

## [2.4.1] - 2026-04-30

### Fixed

- **Serial:** Strip UART/miniterm **ESC** bytes that sit on row boundaries (often shown as a visible “ESC” every line).
- **Terminal prompts:** **#** / **$** / **>** and `user@host:path` now colorize even when the shell sends **SGR/reset** on the same line; **PowerShell / CMD / Unix** also colorize text **after** the prompt on the same line.
- **Welcome banner:** A **56-character `=`** rule, bottom border, and a **double line break** after the block so the first **real** session output always starts on a **new** line, aligned across session types.

## [2.4.0] - 2026-04-29

### Added

- **Welcome banner:** Each terminal session shows a **Welcome to adbnik** header with session type (SSH, ADB shell, Serial, CMD, PowerShell, etc.) and **local date/time**; the same banner appears after **manual reconnect**, auto serial COM restart, and **Reconnect** from the tab menu. Session-specific hints (e.g. ADB device line, serial port line) still appear inside the banner when configured.
- **Prompt readability:** When ANSI uses the default foreground, common **Unix / PowerShell / CMD** prompt lines are split into readable colors (user, host, path, and **`$` / `#` / `>`**).

### Changed

- **Terminal scrolling:** Process output uses **scroll-to-bottom only when the chunk introduces a new line** (`<br/>`), reducing jumpy auto-scroll when long lines **wrap** (SSH, CMD, PowerShell, ADB, serial).
- **View menu:** **Theme** submenu with **Light** and **Dark** (replaces the single **Dark theme** checkbox).
- **Themes:** Softer **light** chrome (less stark white) and **dark** chrome (warmer charcoal, less saturated blue accents); terminal pane uses a slightly softer dark surface.

### Fixed

- **Serial:** Removed stripping of **ESC** bytes from the raw stream (colors/logic depended on ANSI); added scrubbing of leaked **`[0;39m` / `0;39m`**-style text and tighter collapse of **blank lines**.

## [2.3.1] - 2026-04-29

### Fixed

- **Serial terminal:** ANSI/color rendering no longer inserts ~three blank lines per line — stacked `<br/>` from chunked ANSI parsing is collapsed, and excess newline runs are tightened before conversion.
- **Explorer SFTP/FTP auto-reconnect:** Scheduled retries now keep their backoff (reconnect no longer resets the attempt counter at the start of each try); failed SFTP/FTP reconnect attempts schedule further auto-retries; SFTP listing no longer treats a dead connection as an empty folder when both `listdir_attr` and `listdir` fail; borrowed SFTP sessions detect inactive transports before listing; the reconnect timer is started before the disconnect dialog so recovery can run while the message box is open.
- **QThread cleanup:** Remote list worker threads are parented to the explorer page, disconnected and `deleteLater`’d from the done-handler (instead of `finished → deleteLater` alone); ADB device/stats refresh threads are waited on if still running before deletion; async serial COM release waits for the worker before `deleteLater`.

## [2.3.0] - 2026-04-29

### Added

- **SSH terminal resilience:** OpenSSH is invoked with **`ServerAliveInterval` / `ServerAliveCountMax`** so dropped networks tend to close the client process and trigger the same **auto-reconnect** path as other sessions (alongside existing **`TCPKeepAlive`**).
- **Explorer remote resilience:** SFTP/FTP **auto-reconnect** allows more retry rounds (**6** attempts) like ADB-heavy usage patterns.

### Changed

- **Terminal colors (Moba-style):** **SSH, ADB shell, and serial** now use the same **ANSI → HTML** pipeline as **CMD/PowerShell**, so **foreground/256/truecolor** SGR codes render in the scrollback. Remote sessions reuse the **same flush budget** as local HTML output to limit UI stalls.
- **Tab bar menus:** **Terminal** and **File Explorer** session tab context menus use **standard icons**; reconnect/tooltips reference **Ctrl+R** chords; terminal font reset matches the **default 11 pt** session font.
- **Serial auto-reconnect:** When a serial session **ends**, the generic terminal auto-reconnect loop is **not** started (serial keeps its own recover/restart logic).
- **Safer error lines:** Failed process start messages quote argv with **`shlex.quote`** so paths containing spaces are readable.
- **SSH prompts with spaces:** ANSI reset-after-prompt detection allows **paths that contain spaces** before **`$` / `#`**.

## [2.2.0] - 2026-04-29

### Added

- **File Explorer tab bar:** Right-click a session tab for **Close**, **Close others**, **Close to the right**, **Close to the left**, **Close all**, and **Reconnect**.

### Fixed

- **Explorer reconnect prompt:** Remote listing failures now always offer the **Reconnect / New session…** dialog (except standalone permission-denied warnings). **ADB** listings treat stderr-with-errors and empty shell output as failures so disconnects are detected instead of a blank remote pane with only **Up**.
- **Background threads:** Explorer waits longer for transfers/listings/deletes to stop when closing a tab; if something still will not finish, a **clear log message** names the task and suggests opening a new session. Tab pages are **deleteLater**’d after close to avoid leaks.
- **QThread cleanup:** Stopping work before tab removal is more reliable, reducing *QThread: destroyed while thread is still running* issues after long runs.

## [2.1.2] - 2026-04-29

### Added

- **Reconnect shortcuts:** **Ctrl+R** and **Ctrl+Shift+R** both reconnect in **Terminal**, **File Explorer**, and **Screen Control** (case variations of the key are the same on Windows).
- **Explorer disconnect dialog** names the **active session** (e.g. `ADB · <serial>`, `SFTP · user@host`, `FTP · …`) so the correct tab’s failure is obvious when multiple sessions are open.

### Changed

- **Typography & layout:** Larger default UI font (14px), taller main and explorer tab bars, slightly larger file table and path bar text, bigger terminal output (Consolas 11pt), wider screen-control config column, and a roomier **Log** panel with a better default split.
- **Log panel & themes:** The application log is **re-colored when switching light/dark theme** so existing lines stay readable; light mode uses a **light log surface** (no longer a dark “card” in a light window).

## [2.1.1] - 2026-04-29

### Added

- **File Explorer:** Prominent **Reconnect** button in the remote action row (with **Ctrl+R**), plus a **disconnect** dialog when the remote session appears lost (choices: **Reconnect**, **New session…**, **Dismiss**).
- **Keyboard:** **Ctrl+R** reconnects the current session in **Terminal**, **Screen Control**, and **File Explorer** (when that surface has focus in the window).

## [2.0.0] - 2026-04-29

### Added

- **Auto-reconnect controls (core):**
  - Terminal sessions support bounded auto-reconnect with backoff after unexpected disconnect.
  - Screen Control supports bounded auto-reconnect when scrcpy drops unexpectedly.
  - Explorer remote sessions support bounded auto-reconnect attempts after refresh/connect errors.
- **Command palette:** `Ctrl+Shift+P` quick-action launcher for common navigation/reconnect actions.
- **Session health dialog:** quick runtime view of terminal/screen/explorer session health from the command palette.

### Changed

- **Reconnect UX:** reconnect affordances are now available consistently across Terminal tabs, Screen Control, and Explorer remote sessions.
- **Configuration:** new persisted reconnect toggles in config (`auto_reconnect_terminal`, `auto_reconnect_screen`, `auto_reconnect_explorer`).

## [1.4.7] - 2026-04-23

### Added

- **Reconnect options:** Added explicit **Reconnect** actions for all three surfaces after power-off/cable drops:
  - Terminal tabs: right-click session tab -> **Reconnect**
  - Screen Control: **Reconnect** button next to Start/Stop
  - File Explorer: **Reconnect remote session** button in the remote address bar

### Changed

- **Screen status:** Unexpected scrcpy process exits now show **Disconnected — click Reconnect** so recovery is obvious.
- **Terminal status line:** Ended terminal tabs now print a reconnect hint (`right-click tab -> Reconnect`).

## [1.4.6] - 2026-04-23

### Changed

- **Terminal input:** Typing and **Backspace** apply only at the **end** of the current input (after the prompt). You can still **move the caret and select** anywhere for **copy**. Wrapped lines are one logical line — the caret jumps to the true end before characters are inserted or the last character is erased.
- **Enter / Shift+Enter:** Both **commit** the current line; Shift+Enter no longer inserts a second paragraph (that broke wrapped single-line input and commit/delete).

### Fixed

- **Commit / truncation:** Enter always commits and removes the **full** input tail (**anchor → document end**), not only to the caret — fixes truncated or split sends when QTextEdit wrapped the line or the caret was not at the end.

## [1.4.5] - 2026-04-23

### Fixed

- **Terminal input:** Restored correct capture of the **full typed line** when text wraps in the pane — range slicing no longer drops the **last character**, and the input tail uses selection to the **document end** (fixes truncated sends and odd line splits after Enter).
- **SSH / ADB output:** Fewer **stacked blank lines** between chunks (collapse 3+ newlines to one in the plain-text PTY path).
- **Serial:** Opening failure shows **only the error text** (no command dump). Removed the extra blank line injected on **empty Enter**. Shortened automatic **retry** notices.

## [1.4.4] - 2026-04-23

### Changed

- **Bookmarks:** Opening a bookmark from the sidebar sets the **session tab title** to **name · kind · details** (e.g. SSH host, ADB serial, serial COM @ baud, local CMD/PowerShell).

### Fixed

- **Terminal display:** Restored **wrap at pane width** for ADB/SSH/serial sessions (removed forced **NoWrap**) so long output and input **wrap within the window** instead of truncating until horizontal scroll.
- **Serial / multiple COM ports:** Windows cleanup of orphan **miniterm** processes now matches the COM port with a **word boundary** (e.g. **COM3** no longer matches **COM30** / **COM31**), so closing or retrying one port does not kill sessions on nearby port numbers.

## [1.4.3] - 2026-04-23

### Changed

- **Terminal / serial:** Automatic COM-port retry moves **taskkill / miniterm cleanup and pacing sleeps** to a **worker thread** so the UI thread is not blocked for seconds during reopen.
- **Screen / scrcpy:** Automotive **UHID** inference uses a full **`adb shell getprop`** snapshot (with fallback to targeted props) plus extra keywords — fewer IVI head units misclassified as phones.

### Fixed

- **ADB / SSH / serial display:** Remote PTY and **serial** panes now lock **WordWrapMode** and **QTextOption** to **NoWrap** (not only `QTextEdit` line wrap), so long tokens are not split across visual rows; font zoom reapplies the same constraint.
- **ADB workers:** Device list and stats threads deliver **`done`** via **QueuedConnection** so slots always run on the GUI thread.

## [1.4.2] - 2026-04-23

### Changed

- **Screen / scrcpy:** **Keyboard mode is fully automatic** (IVI/automotive → **UHID** via ADB inference). The Screen tab **no longer shows a keyboard dropdown**; override only via **Extra CLI** (e.g. ``--keyboard sdk``) if needed.
- **Terminal tabs:** Only the **active** session runs the output flush timer — **background ADB/SSH tabs** stop consuming CPU while you work elsewhere (faster tab switching).
- **ADB workers:** **Stale** device-list / stats **QThread** instances from an older refresh are always **deleteLater**’d so Qt does not tear down live threads incorrectly.

### Fixed

- **ADB / SSH display:** Remote PTY panes also set the document **text wrap mode** to **NoWrap** (in addition to ``QTextEdit``), so long commands stay on **one visual line**.
- **Serial retry:** Removed automatic **PnP disable/enable** for busy COM ports — it **blocked the UI** for a long time and could leave the port **stuck disabled**. Retry now relies on killing miniterm/orphans and reopening (same guidance text if still busy).
- **Shutdown:** **MainWindow** sets a **shutting-down** flag so no new ADB refresh/stats threads start during close; worker pointers are **cleared** after **wait/terminate**.

## [1.4.1] - 2026-04-23

### Added

- **ADB device inference** for **scrcpy keyboard**: default **Auto** selects **UHID** when ``getprop`` / ``pm list features`` suggest IVI/automotive; phones keep SDK injection without manual toggling.

### Changed

- **ADB / SSH terminal:** **No word-wrap** on remote PTY panes — long commands stay on **one visual line** (horizontal scroll). Commit behavior unchanged.
- **Performance:** caret **blink disabled** app-wide; remote/serial terminal flush timers slightly **coarser**; removed nested ``processEvents`` during PTY redraw; **File Explorer** coalesces ``processEvents`` (~13 Hz) so tab switches stay responsive under SFTP/FTP progress.

### Fixed

- **QThread lifecycle:** ADB refresh/stats worker threads use a proper parent, **no** ``finished → deleteLater`` race on the live object; finished handlers **deleteLater** the worker; shutdown **waits** longer and **terminates** only after a timeout — avoids “QThread: Destroyed while thread is still running”.
- **Repository hygiene:** removed legacy per-version **RELEASE_NOTES_v\*.md** stubs from ``.github`` (changelog remains in ``CHANGELOG.md``).

## [1.4.0] - 2026-04-23

### Added

- **Screen / scrcpy:** **Keyboard** mode selector — **Default (SDK)** (unchanged for phones) or **UHID** for many **infotainment / IVI** head units where key events do not reach apps. **SDK (explicit)** is also available. Setting is saved in config. *Extra CLI* with your own `--keyboard` still wins and is not overridden.

### Fixed

- **ADB / SSH terminal:** Committed command line **collapses internal line/paragraph breaks** to a single line of text (QTextEdit wrap + block boundaries no longer split a long command or send only the first segment after Enter).
- **Terminal wrap:** Word wrap prefers **word boundaries** when possible (less mid-token line breaks; long tokens may still wrap if needed).
- **SSH / ADB stream:** Lone **carriage return after `$` / `#` / `>`** is treated as same-line redraw (fixes `#` and `ls` splitting onto separate rows when the PTY echoes that way).
- **SSH / ADB stream:** **Fewer stacked blank lines** between chunks (leading glue newline not duplicated when the chunk already starts with `\n`; triple+ blank runs collapsed to at most one empty line).
- **Serial:** Extra cleanup for **orphan reset fragments** (`0;39m`, `[0;39m`, bracket variants) on their own line.

## [1.3.10] - 2026-04-23

### Changed

- **Packaging / repo:** Single-package workspace layout (no nested extra copy); standard ignores for build outputs. Same application code as 1.3.9.

## [1.3.9] - 2026-04-20

### Fixed

- **SSH / ADB terminal:** When the PTY did not send a newline between the end of command output and the next prompt (or between an echoed command and the following output), lines could appear **glued** (e.g. ``vendor_dlkm`` + next prompt on one row, or ``# ls`` + ``bin`` as ``lsbin``). The stream now inserts a **newline** before a chunk that **starts like a shell prompt** or when the scrollback tail **ends with prompt + echoed command** without a trailing newline.
- **Commands → SSH:** Quick commands are sent to a **running SSH terminal tab**, not whichever session tab is active (so they no longer run in an ADB or local shell tab by mistake). If the active tab is SSH, that tab is used; otherwise the first running SSH tab is focused and receives the line.

## [1.3.8] - 2026-04-20

### Fixed

- **SSH / ADB terminal:** Lone PTY carriage returns are mapped to **newlines** again (not spaces). Treating ``\\r`` as a space had glued prompts and output onto one line (e.g. repeated ``#`` on the same row) and produced an on/off “stuck together” look as chunks alternated. Real line breaks still come from ``\\r\\n`` / ``\\n``; long runs of blank lines from redraws remain capped.

## [1.3.7] - 2026-04-20

### Fixed

- **SSH / ADB terminal:** `strip_ansi_for_display` now removes **SGR** (`…m`) sequences only; **all other CSI** (cursor movement, erase, modes, etc.) becomes a **single space**. Stripping non-SGR CSI to empty collapsed cursor spacing and reproduced **`lsbin`**-style glue after the first command.
- **SSH / ADB terminal:** Removed the **synthetic newline** injected on **empty Enter** (serial UART still gets it). The extra `\n` stacked with PTY echo and looked like blank line / input / blank line per Enter.

## [1.3.6] - 2026-04-20

### Fixed

- **SSH / ADB terminal:** Lone `\r` and erase-line / erase-display ANSI codes are mapped to a **space** instead of a **newline**, so echoed input and the next output stay visually separated without extra blank lines. (Newlines still come from real `\n` / `\r\n` from the PTY.)
- **Serial console:** Removed the remote-PTY newline normalizer from the UART path so serial output matches prior density (no extra line breaks from `\r` → `\n`).

## [1.3.5] - 2026-04-20

### Fixed

- **SSH / ADB plain terminal:** When stripping ANSI for display, **erase-line (EL)** and **erase-display (ED)** sequences are turned into a **newline** before other CSI removal. Removing them entirely had collapsed echoed text into the next run on later commands (e.g. `ls` + EL + `bin` rendered as `lsbin`).

## [1.3.4] - 2026-04-20

### Fixed

- **SSH / ADB / serial terminal:** Replaced CR “overwrite” simulation with **mapping lone `\r` to `\n`** after ANSI stripping (QTextEdit cannot emulate true TTY overwrite; the previous approach cleared lines and made prompts/output look wrong). Long runs of blank lines from spinner redraws are **capped** to limit vertical spam.
- **File Explorer (SFTP/FTP):** Drag-and-drop pull completion now uses the same **“Pull complete” dialog** (Open / OK) as the **Pull** toolbar action, then opens the default app for a single pulled file the same way as after a toolbar pull.

## [1.3.3] - 2026-04-19

### Fixed

- **SSH / ADB / serial terminal:** Carriage return is handled as **return-to-start-of-line** (overwrite) instead of mapping every lone `\r` to a newline. That removes the blank-line spam from progress-style output, avoids glued tokens without relying on extra `\n` injection, and keeps spacing consistent with normal TTY behavior.
- **SSH quick commands:** `send_line(..., sync_anchor_after=True)` is only used for **Commands → SSH** menu lines; the default path no longer schedules a delayed anchor sync for unrelated callers.
- **File Explorer (SFTP/FTP):** The transfer `done` handler no longer depends on `sender()` (unreliable with queued cross-thread signals). The emitting thread is captured in the connection so **open after pull** runs reliably for drag-and-drop and batch transfers. Pulled **folders** are opened in the system file manager when included in the completion list.

## [1.3.2] - 2026-04-19

### Fixed

- **File Explorer (SFTP/FTP):** Drag-and-drop pull now opens downloaded file(s) like the Pull button: the transfer thread reports pulled file paths, and the UI opens them after a short deferred pass (same timing fix as refresh settling).
- **SSH quick commands:** Removed the extra injected newline before menu-sent lines (which produced stray `#` / blank lines). After sending, the input cursor and anchor move to the document end on a short delay so the caret sits on the new prompt line after the shell responds.

## [1.3.1] - 2026-04-19

### Fixed

- **Terminal:** `TerminalTab` no longer calls `_reload_bookmark_sidebar()` before `self.tabs` is created (avoid `AttributeError: ... has no attribute 'tabs'` on startup). Guard added in `_refresh_bookmark_open_indicators` for safety.

## [1.3.0] - 2026-04-19

### Fixed

- **SSH / ADB plain-text terminal:** Lone carriage returns from the PTY are treated as line breaks so command output no longer glues to the typed command (e.g. `ls` + `bin` no longer appears as `lsbin`).
- **SSH quick commands (Commands → SSH):** Injected lines force a clean line before sending so the remote prompt character does not stick to the end of the command.
- **File Explorer (SFTP/FTP):** Single-file pull uses the active session again (a mistaken early return had sent all SFTP/FTP pulls through a secondary connection and skipped the inline path). After a successful single-file pull, the file is opened with the default app when possible; batch pull opens the last file if it is a file.

### Changed

- **Terminal tabs:** Session tab labels are color-coded (ADB green, SSH blue, serial yellow, local shells light gray). ADB shell tabs use the Android-style bookmark icon; **Session → ADB** and **Commands → ADB** menus use the same icon.
- **Bookmarks:** Sidebar bookmark names turn **green** when a matching session tab is open and **red** when it is not.
- **Hints:** Shortened or removed long “how to start” blocks on Terminal, File Explorer, and Screen Control (details live in the user guide).
- **Application log:** Timestamp includes the date; rows are easier to scan with light- and dark-theme colors and a short placeholder explaining tags.

## [1.2.0] - 2026-04-19

### Added

- **Help menu:** **Website**, **User guide** (F1), **GitHub**, **PyPI**, plus **About** (with the same links). Central URL constants in `adbnik/urls.py`.
- **User guide (site):** New section **ADB and scrcpy on your PC** on the guide home page (`guide/index.html#adb-scrcpy`) — PATH vs full paths vs a portable tools folder, tied to **File → Preferences**. **GitHub** link added to the guide header on every guide page. Terminal / Explorer / Screen pages slightly expanded with clearer step-by-step wording.

### Changed

- **Preferences** dialog: clearer intro text for executable paths (own install vs bundled/portable folder).
- **About** box: link row and slightly plainer wording (e.g. tips section).

## [1.1.1] - 2026-04-19

### Added

- **User guide (website):** New section at **[nvnkennedy.github.io/adbnik/guide/](https://nvnkennedy.github.io/adbnik/guide/)** — dedicated pages for **Terminal** (menu bar, sidebar, tabs, shortcuts), **File Explorer** (local/remote panes, toolbar actions, keyboard), and **Screen Control** (step-by-step scrcpy flow, every mirror option, ADB buttons, embed vs separate window). Linked from the landing page, README, and PyPI **Documentation** URL.

## [1.0.2] - 2026-04-19

### Changed

- **Project website** (GitHub Pages): New production-style landing page under `docs/` — responsive layout, feature overview, install snippet, screenshots, and footer links. Add `.nojekyll` so static assets deploy correctly.

## [1.0.1] - 2026-04-19

### Fixed

- **Windows `adbnik-setup`:** Interactive runs no longer show a black console window before the folder dialog (`FreeConsole`); errors use a message box. Use `adbnik-setup --folder ...` when you need printed output in a terminal.

## [1.0.0] - 2026-04-19

First stable release under semantic versioning.

### Added

- **Windows `adbnik-setup`:** After `pip install adbnik`, run `adbnik-setup` to place an **Adbnik** shortcut (chosen folder, same Python as `pip`, app icon cached under `%LOCALAPPDATA%\Adbnik\`). Options: `--folder`, `--name`.
- **File explorer:** **Rename** (context menu, toolbar, **F2**) for local and remote items (ADB `mv`, SFTP/FTP rename). **Backspace** navigates up in the panes but **does not** steal keys while renaming or typing in **New file/folder** dialogs (dialogs parented to the main window).
- **Terminal:** Tab bar **Increase / Decrease / Reset font size** applies to **existing** scrollback (HTML output), not only new text.

### Changed

- **README** and **PyPI** metadata: production-oriented copy; distinct **Homepage**, **Repository**, **Documentation**, and **Changelog** URLs; name etymology (**ADB** + **-nik**, as in *technik*).

### Fixed

- **Explorer:** **Backspace** no longer conflicts with **QInputDialog** text fields when the dialog was parented to the session page.

## [0.7.0] - 2026-04-19

### Fixed

- **SSH / ADB / serial terminals:** Stopped inserting a **synthetic newline after every Enter** on remote PTY sessions (shell already echoes line endings) — removes stacked `#` prompts, split commands, and double-spaced `ls` output. Tightened newline collapsing in the PTY path and in ANSI/serial preprocessors.
- **Serial UART logs:** Fewer blank lines between log records; PnP COM reset wait shortened slightly.
- **SFTP:** `rmdir` treats **ENOENT** as success (race / already removed). **`mkdir -p`** uses one shared implementation that only ignores true “exists” errors and surfaces bad `stat` results.
- **Horizontal scrolling:** Terminal uses **word wrap at widget width** instead of `NoWrap`.
- **Idle “Not responding”:** **ADB device + stats timers pause** when the app is in the **background**; device stats label updates are scheduled with **`qt_thread_updater.call_latest`**. Less frequent `processEvents` during remote PTY flush.

## [0.6.0] - 2026-04-19

### Fixed

- **Terminal (SSH/ADB):** Removed per-chunk newline injection and **stopped turning lone `\r` into `\n`** (fixes **slog2info** and similar tools splitting tokens across lines). Carriage returns used for same-line redraw are stripped; only `\r\n` becomes `\n`. PTY blank-line collapse now targets **three or more** newlines (fewer spurious joins).
- **SFTP delete:** Recursive delete uses **`sftp_listdir_attr_safe`**, raises clear errors instead of failing silently on `stat`, handles **directory misclassified as file** (`EISDIR` / message), and runs on a **worker thread** so the window stays responsive. Refresh after success is scheduled with **`qt_thread_updater.call_latest`**.

### Notes

- **SFTP client sharing:** Avoid starting other SFTP operations on the same session while a background delete runs.

## [0.5.0] - 2026-04-19

### Fixed

- **SSH terminal:** Output no longer starts on the same line as the prompt after Enter (relaxed “at prompt” newline bridging; leading newline when the PTY buffer does not end with `\n`; `\r` normalized to `\n`).
- **Responsiveness:** Smaller plain-text flush batches, slightly faster flush timer, and periodic `processEvents(ExcludeUserInputEvents)` during heavy SSH/ADB streams so tab switching stays usable.
- **Dark theme / preferences:** Theme application is scheduled via **`qt_thread_updater.call_latest`** (global updater started after `QApplication`) so toggling theme after heavy sessions is less likely to block the UI.
- **SFTP / FTP explorer:** Recursive FTP delete restores directory context between children; **RFC 959–style quoting** for `CWD`, `MKD`, `RMD`, `DELE`, `STOR`, `RETR` so paths with **spaces or quotes** work for list, delete, mkdir, upload, download, and new file.
- **SFTP mkdir:** `mkdir` failures are no longer silently ignored; “already exists” is handled explicitly.

### Added

- Dependencies: **`qt-thread-updater`**, **`QtPy`** (required by qt-thread-updater; `QT_API=pyqt5` set at startup).

### Notes

- Terminal **byte order** is unchanged: streaming still uses the existing coalesced flush (not `call_latest`), which would drop chunks.

## [0.4.9] - 2026-04-19

### Fixed

- **SSH / ADB shell (critical):** Continuous tools like **slog2info** no longer freeze the UI. Those sessions now render with **`QTextCursor.insertText`** on **plain text** after **`strip_ansi_for_display`** — the old **`insertHtml`** ANSI path cannot stay responsive at Moba-like data rates inside `QTextEdit`. **Inline ANSI colors are not drawn** in SSH/ADB tabs in exchange for stable frame times; local CMD/PowerShell still use colored HTML where volume is lower.
- **Serial:** Extra stripping of orphan **`0;39m` / `[0;39m`** (including without a leading bracket) in **`preprocess_serial_stream`** and in **`strip_ansi_for_display`**.
- Removed **`processEvents`** from the flush path (plain rendering reduces need; avoids reentrancy risk).

### Notes

- **`qt-thread-updater` / `call_latest`:** Not used for streaming output — it **drops intermediate chunks**, which would corrupt terminal order. Decode/drain stay on the UI thread; cost moved to **cheap plain append** instead of HTML.

## [0.4.7] - 2026-04-19

### Fixed

- **Terminal (SSH / ADB shell):** Heavy streams like **slog2info** no longer freeze the window: **capped HTML per flush**, **adaptive flush intervals**, **backpressure** on stdout decode when the HTML backlog is large, **less frequent** `ensureCursorVisible`, **smaller scrollback** block cap, and periodic **`processEvents(ExcludeUserInputEvents)`** so Windows stays responsive.
- **ANSI:** Embedded terminal **ignores ANSI background** colors (no full-pane blue/green from remote logs) and **lifts SGR black (30)** to a readable gray on dark UIs.
- **Serial:** Strip corrupted **`[0.39m`** fragments; **filter pySerial miniterm banner** lines; tab titles use **“Serial console”**; default banner explains **Ctrl+]** (telnet break) without relying on miniterm’s own “Quit” line.

## [0.4.6] - 2026-04-19

### Fixed

- **SSH:** Empty host no longer launches a broken two-argument ``ssh -tt`` session (which could surface as confusing errors such as banner exchange / **port -1**). Missing host now uses a clear in-terminal message, or a deterministic placeholder target when unavoidable; **SessionProfile** ports are coerced in ``__post_init__`` so bad saved values never reach ``ssh -p``.
- **SSH bookmarks:** Empty **host** is rejected with a dialog; **port** is normalized with ``normalize_tcp_port``.
- **Serial:** **stderr is merged into stdout** for miniterm so open failures (permission / access) always hit the same output path; recoverable errors include more **permission / errno** patterns; **QProcess** start errors that match those patterns trigger the same **auto-retry + optional COM PnP reset** path as a busy port.

## [0.4.5] - 2026-04-19

### Fixed

- **Terminal (ADB shell + SSH):** Shared **`_is_remote_pty_shell`** path so both session types get the same behavior: **merged stderr→stdout**, **bulk stdout drain** (~2 MB per tick), **coalesced flush** timer, **capped scrollback**, **throttled** scroll during HTML append, **ANSI reset** after prompt-like lines and on session end, and **prefetch** of Tab-completion listings shortly after connect.
- **Tab completion:** **ADB shell** completion runs **off the UI thread**; results are delivered with **`pyqtSignal`** (same as **SSH**), avoiding unsafe `QTimer` use from worker threads.
- **PTY output:** **SSH** uses the same **tightened PTY chunk** handling as ADB for fewer stray blank lines before command output.

### Changed

- Internal: one **`_remote_ui_tick`** counter for SSH and ADB heavy-stream throttling (no duplicated logic).

## [0.4.4] - 2026-04-19

### Fixed

- **SSH:** Merge **stderr into stdout** for the OpenSSH `QProcess` so a noisy remote (e.g. `slog2info` writing to stderr) cannot fill the stderr pipe and stall or prolong the session compared to other clients.
- **SSH UI:** **Bulk drain** of pending stdout (up to ~2 MB per timer tick), slightly slower flush timer, and **capped scrollback** (`maximumBlockCount`) so heavy log streams stay smoother; **throttled** `ensureCursorVisible` during SSH flushes (the HTML append path no longer forces a full scroll on every chunk).

### Changed

- **SSH Tab completion:** Remote command pool still includes **`/ifs/bin`** and **`$PATH`** (from prior release); helper `ssh` subprocess remains **below-normal** priority on Windows so the Qt UI stays responsive.

## [0.4.3] - 2026-04-19

### Fixed

- **Serial:** Strip **ESC (0x1b)** and **C1 CSI (0x9b)** at the **byte** level before decode, plus a final string pass, so Qt never paints the visible “ESC” glyph on UART output (e.g. before `C2:` lines).
- **SSH:** **Tab completion** (`ls` / `$PATH` listing) runs in a **background thread** so the UI and remote shell stay responsive — long completions no longer feel like a hung session (e.g. while `slog2info` or other tools are running). If completion finds nothing, a real Tab is sent to the remote shell.

### Changed

- **Terminal performance:** Larger read chunks and faster flush coalescing for **serial**; batched `setUpdatesEnabled` around flush; slightly tuned **SSH** chunk/flush intervals.

## [0.4.2] - 2026-04-19

### Fixed

- **SSH:** Removed OpenSSH **ControlMaster** / **ControlPath** (regression in 0.4.1). Those options caused ``getsockname failed: Not a socket`` after login when using the Windows OpenSSH client under Qt ``QProcess``.
- **Serial:** More reliable teardown — longer waits, **taskkill** fallback, and a PowerShell sweep that stops any stray ``python -m serial.tools.miniterm`` still holding the same COM port so the tab can reconnect after close or auto-retry.
- **Serial ANSI:** Dropped an over-aggressive escape strip that broke OSC handling after ``preprocess_escape_noise``; stray ESC / bracket noise should still be cleaned without corrupting sequences.

## [0.4.1] - 2026-04-19

### Fixed

- Terminal: strip lone ESC bytes and orphan `[0;39m` noise for ADB/local shells (same pipeline as SSH), reducing stray “ESC” / reset glyphs.
- SSH: OpenSSH **ControlMaster** for interactive sessions; Tab-completion `ssh` calls attach via **ControlPath** so listings reuse the live session (faster on QNX). Command pool uses remote **`$PATH`** only (no hardcoded bin directories), shorter timeouts, longer cache TTL.
- Qt: **QThread** slot races fixed (ignore stale `done` from an older thread after a new refresh/transfer/stats run); disconnect thread signals before terminate on explorer shutdown.
- Serial (Windows): on the first miniterm restart after a port error, attempt **disable/enable** the COM device via PowerShell (PnP), matching a manual Device Manager reset.

## [0.2.9] - 2026-04-09

### Changed

- **README** and **GitHub Pages** show real **UI screenshots** (`docs/screenshots/*.png`) on GitHub and PyPI (absolute `raw.githubusercontent.com` URLs).

## [0.2.3] - 2026-04-11

### Changed

- **App icon** follows light/dark UI: light theme uses a light “card” icon; dark theme uses the slate tile. Taskbar/window icon updates when you toggle **View → Dark theme**.

## [0.2.2] - 2026-04-11

### Changed

- New **Adbnik** window icon (slate tile, teal accent, “A” mark)—replacing the older generic device-style glyph.
- **Version** shown in the **status bar** (bottom-right) and in **Help → About** (title + body).

## [0.2.1] - 2026-04-11

### Changed

- README rewritten for end users: what Adbnik does, install, first run, and Windows `ModuleNotFoundError: adbnik` troubleshooting.

### Fixed

- Packaging metadata description shortened; version aligned across `pyproject.toml` and `adbnik.__version__`.

## [0.2.0] - 2026-04-09

### Changed

- **Product and PyPI name:** **`adbnik`**. Console command: **`adbnik`**. Python import package: **`adbnik`** (replacing `devicedeck` / `adbsshscreen` / `adbsshdeck` naming).
- User settings file default: **`~/.adbnik.json`**, with automatic migration from **`~/.devicedeck.json`** when present.
- Windows build output: **`dist/Adbnik/`**, **`Adbnik.exe`**, installers **`Adbnik_Setup_*.exe`**.
- GitHub Pages and repository URLs target **`adbnik`** (rename the GitHub repo to match).

## [0.1.1] - 2026-04-09

### Changed

- Earlier PyPI distribution names (`adbsshdeck`, etc.) and import package `devicedeck` (superseded by 0.2.0).

## [0.1.0] - 2026-04-09

### Added

- Production packaging pipeline with PyInstaller (`adbnik.spec`).
- Windows installer icon embedding and no-console subprocess handling.
- Release helper scripts and release docs.
- GitHub Pages-ready website content under `site/`.

### Fixed

- Prevented repeated visible CMD windows in packaged app by hiding Windows subprocess windows for background commands.
- Improved process cleanup for terminal/scrcpy lifecycle on app close.

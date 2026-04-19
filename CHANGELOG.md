# Adbnik Changelog

All notable changes to this project are documented in this file.

The format loosely follows Keep a Changelog and Semantic Versioning.

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

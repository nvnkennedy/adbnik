import os
import re
import shlex
import subprocess
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

_adb_proc_lock = threading.Lock()
_active_adb_procs: List["subprocess.Popen"] = []


def register_adb_process(proc: "subprocess.Popen") -> None:
    """Track spawned adb child processes so shutdown/cancel can terminate them."""
    with _adb_proc_lock:
        if proc not in _active_adb_procs:
            _active_adb_procs.append(proc)


def unregister_adb_process(proc: "subprocess.Popen") -> None:
    with _adb_proc_lock:
        try:
            _active_adb_procs.remove(proc)
        except ValueError:
            pass


def kill_all_adb_subprocesses() -> None:
    """Kill every registered ``Popen`` (push/pull/measure) — used on app close or hard cancel."""
    with _adb_proc_lock:
        snap = list(_active_adb_procs)
    for p in snap:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass


def _win_subprocess_flags() -> dict:
    """Hide spawned console windows for background commands on Windows."""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def run_command(command: List[str], timeout: int = 20) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            **_win_subprocess_flags(),
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"


def run_adb(adb_path: str, args: List[str], timeout: int = 20) -> Tuple[int, str, str]:
    return run_command([adb_path, *args], timeout=timeout)


# adb push/pull often prints percentages like: 12%  |  12.3%  |  [ 45% ]  |  45/100
_PCT_PATTERNS = (
    re.compile(r"(?:^|[^\d])(\d{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"(\d{1,3})\s*/\s*100"),
)


def _best_percent_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    best = -1
    for rx in _PCT_PATTERNS:
        for m in rx.finditer(text):
            try:
                v = float(m.group(1))
                p = int(round(v))
                if 0 <= p <= 100:
                    best = max(best, p)
            except ValueError:
                continue
    return best if best >= 0 else None


def _split_stream_buffer(buf: str) -> Tuple[List[str], str]:
    """Split *buf* into complete lines delimited by ``\\r`` or ``\\n`` (handles ``\\r\\n``)."""
    lines: List[str] = []
    i = 0
    n = len(buf)
    start = 0
    while i < n:
        c = buf[i]
        if c == "\r":
            lines.append(buf[start:i])
            i += 1
            if i < n and buf[i] == "\n":
                i += 1
            start = i
            continue
        if c == "\n":
            lines.append(buf[start:i])
            i += 1
            start = i
            continue
        i += 1
    return lines, buf[start:]


def adb_remote_probe_size(adb_path: str, shell_prefix: List[str], remote_path: str) -> Tuple[Optional[int], str]:
    """
    Best-effort size of a remote path before transfer.
    Returns (bytes, kind) where kind is: file | dir | unknown
    """
    rp = (remote_path or "").strip()
    if not rp:
        return None, "unknown"
    q = shlex.quote(rp)
    inner = (
        f"if [ -d {q} ]; then echo D; "
        f"du -sk {q} 2>/dev/null | head -n1 | awk '{{print $1}}'; "
        f"elif [ -f {q} ] || [ -L {q} ]; then echo F; stat -c %s {q} 2>/dev/null; "
        f"else echo U; fi"
    )
    code, out, _ = run_adb(adb_path, [*shell_prefix, "shell", inner], timeout=180)
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    if not lines:
        return None, "unknown"
    kind_tok = lines[0].strip()
    if kind_tok not in ("D", "F"):
        return None, "unknown"
    if len(lines) < 2:
        return None, "unknown"
    try:
        raw = lines[1].strip().split()[0]
        n = int(raw)
    except Exception:
        return None, "unknown"
    if kind_tok == "D":
        return n * 1024, "dir"
    return n, "file"


def adb_remote_path_bytes_now(adb_path: str, shell_prefix: List[str], remote_path: str) -> Optional[int]:
    """
    Current bytes still present at *remote_path* (file size, or ``du`` for directories).
    Returns ``None`` if the path does not exist (fully deleted).
    """
    rp = (remote_path or "").strip()
    if not rp:
        return None
    q = shlex.quote(rp)
    inner = (
        f"if [ ! -e {q} ]; then echo N 0; "
        f"elif [ -d {q} ]; then kb=$(du -sk {q} 2>/dev/null | head -n1 | awk '{{print $1}}'); echo D ${{kb:-0}}; "
        f"else sz=$(stat -c %s {q} 2>/dev/null); echo F ${{sz:-0}}; fi"
    )
    code, out, _ = run_adb(adb_path, [*shell_prefix, "shell", inner], timeout=45)
    parts = (out or "").strip().split()
    if len(parts) < 2:
        return None
    kind_tok, val = parts[0], parts[1]
    if kind_tok == "N":
        return None
    try:
        n = int(float(val))
    except ValueError:
        return None
    if kind_tok == "D":
        return n * 1024
    if kind_tok == "F":
        return n
    return None


def adb_start_rm_rf(adb_path: str, shell_prefix: List[str], target: str) -> subprocess.Popen:
    """Start ``adb shell rm -rf …`` without waiting (used with ``adb_remote_path_bytes_now`` polling)."""
    q = shlex.quote((target or "").strip())
    shell_cmd = f"rm -rf {q}"
    proc = subprocess.Popen(
        [adb_path, *shell_prefix, "shell", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **_win_subprocess_flags(),
    )
    register_adb_process(proc)
    return proc


def _adb_remote_file_bytes(adb_path: str, shell_prefix: List[str], remote_path: str) -> Optional[int]:
    q = shlex.quote(remote_path)
    code, out, _ = run_adb(adb_path, [*shell_prefix, "shell", f"stat -c %s {q} 2>/dev/null"], timeout=45)
    try:
        return int((out or "").strip().split()[0])
    except Exception:
        return None


def _adb_remote_dir_bytes_du(adb_path: str, shell_prefix: List[str], remote_path: str) -> Optional[int]:
    q = shlex.quote(remote_path)
    code, out, _ = run_adb(
        adb_path,
        [*shell_prefix, "shell", f"du -sk {q} 2>/dev/null | head -n1 | awk '{{print $1}}'"],
        timeout=180,
    )
    try:
        kb = int((out or "").strip().split()[0])
        return kb * 1024
    except Exception:
        return None


def _local_path_bytes(path: str) -> int:
    try:
        if os.path.isdir(path):
            total = 0
            for dp, _dn, fns in os.walk(path):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            return total
        return os.path.getsize(path)
    except OSError:
        return 0


def _poll_transfer_written_bytes(
    *,
    mode: str,
    adb_path: str,
    shell_prefix: List[str],
    remote: str,
    local: str,
) -> Optional[int]:
    mode = (mode or "").strip()
    try:
        if mode == "push_file":
            return _adb_remote_file_bytes(adb_path, shell_prefix, remote)
        if mode == "push_dir":
            return _adb_remote_dir_bytes_du(adb_path, shell_prefix, remote)
        if mode == "pull_file":
            return _local_path_bytes(local)
        if mode == "pull_dir":
            return _local_path_bytes(local)
    except Exception:
        return None
    return None


def run_adb_with_line_callback(
    adb_path: str,
    args: List[str],
    timeout: int = 600,
    on_line: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
    *,
    poll_total_bytes: int = 0,
    poll_mode: str = "",
    poll_remote: str = "",
    poll_local: str = "",
    adb_shell_prefix: Optional[List[str]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Tuple[int, str, str]:
    """
    Run adb merging stderr into stdout.

    Emits callbacks for complete lines split on ``\\r`` / ``\\n`` (progress bars often use ``\\r``).
    Optional *poll_* parameters enable **byte-based** progress while the transfer runs by periodically
    measuring the growing destination (``stat``/``du`` on device for push; local file/tree size for pull).
    """
    cmd = [adb_path, *args]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=0,
            **_win_subprocess_flags(),
        )
    except FileNotFoundError:
        return 127, "", f"Command not found: {adb_path}"

    register_adb_process(proc)
    out_chunks: List[str] = []
    shell_prefix = list(adb_shell_prefix or [])
    stop_poll = threading.Event()

    lock = threading.Lock()
    last_pct = -1  # -1: no numeric percent yet
    poll_floor = -1  # monotonic floor for byte-poll so du/stat jitter cannot decrease the bar

    def emit_working_if_needed() -> None:
        """Match legacy behaviour: nudge UI while adb hasn't printed a percent yet."""
        if on_percent is None:
            return
        with lock:
            cur = last_pct
        if cur < 0:
            on_percent(-1)

    def merged_on_percent(p: int) -> None:
        nonlocal last_pct
        if on_percent is None:
            return
        if p < 0:
            # -1 means "still working" for the UI; do not clobber numeric progress.
            with lock:
                if last_pct >= 0:
                    return
            on_percent(-1)
            return
        with lock:
            if p > last_pct:
                last_pct = p
                p_out = p
            else:
                p_out = None
        if p_out is not None:
            on_percent(p_out)

    def reader() -> None:
        assert proc.stdout is not None
        pending = ""
        while True:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            chunk = proc.stdout.read(8192)
            if not chunk:
                break
            out_chunks.append(chunk)
            pending += chunk
            lines, pending = _split_stream_buffer(pending)
            for line in lines:
                emit_working_if_needed()
                if on_line and line:
                    on_line(line)
                bp = _best_percent_from_text(line)
                if bp is not None:
                    merged_on_percent(bp)
        if pending:
            out_chunks.append(pending)
            emit_working_if_needed()
            if on_line:
                on_line(pending)
            bp = _best_percent_from_text(pending)
            if bp is not None:
                merged_on_percent(bp)
        try:
            proc.stdout.close()
        except Exception:
            pass

    t_reader = threading.Thread(target=reader, daemon=True)
    t_reader.start()

    poll_sleep = 1.25 if poll_mode in ("push_dir", "pull_dir") else 0.75

    def poller() -> None:
        nonlocal poll_floor
        if poll_total_bytes <= 0 or not poll_mode:
            return
        total = int(poll_total_bytes)
        if total <= 0:
            return
        while not stop_poll.is_set() and proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                break
            cur = _poll_transfer_written_bytes(
                mode=poll_mode,
                adb_path=adb_path,
                shell_prefix=shell_prefix,
                remote=poll_remote,
                local=poll_local,
            )
            if cur is not None and cur >= 0:
                raw = int(min(99, (cur * 100) / total))
                with lock:
                    if raw < poll_floor:
                        raw = poll_floor
                    else:
                        poll_floor = raw
                merged_on_percent(raw)
            time.sleep(poll_sleep)

    t_poll: Optional[threading.Thread] = None
    if poll_total_bytes > 0 and poll_mode:
        t_poll = threading.Thread(target=poller, daemon=True)
        t_poll.start()

    try:
        deadline = time.monotonic() + float(timeout)
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            if time.monotonic() >= deadline:
                stop_poll.set()
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(5)
                except Exception:
                    pass
                unregister_adb_process(proc)
                return 124, "".join(out_chunks), "Command timed out"
            time.sleep(0.12)
    finally:
        stop_poll.set()
        if t_poll is not None:
            t_poll.join(timeout=2.0)
    try:
        t_reader.join(timeout=5.0)
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass
    unregister_adb_process(proc)
    if cancel_event is not None and cancel_event.is_set():
        return 130, "".join(out_chunks), "Cancelled"
    code = int(proc.returncode if proc.returncode is not None else 0)
    if code == 0 and poll_total_bytes > 0 and poll_mode and on_percent:
        merged_on_percent(100)
    return code, "".join(out_chunks), ""

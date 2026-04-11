import re
import subprocess
import threading
import sys
from typing import Callable, List, Optional, Tuple


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


_pct_re = re.compile(r"(\d{1,3})\s*%")


def run_adb_with_line_callback(
    adb_path: str,
    args: List[str],
    timeout: int = 600,
    on_line: Optional[Callable[[str], None]] = None,
    on_percent: Optional[Callable[[int], None]] = None,
) -> Tuple[int, str, str]:
    """Run adb merging stderr into stdout; invoke on_line per line and on_percent when N%% is seen."""
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
            bufsize=1,
            **_win_subprocess_flags(),
        )
    except FileNotFoundError:
        return 127, "", f"Command not found: {adb_path}"

    out_chunks: List[str] = []

    def reader():
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            out_chunks.append(line)
            if on_line:
                on_line(line.rstrip("\n"))
            if on_percent:
                for m in _pct_re.finditer(line):
                    try:
                        p = int(m.group(1))
                        if 0 <= p <= 100:
                            on_percent(p)
                    except ValueError:
                        pass
        proc.stdout.close()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return 124, "".join(out_chunks), "Command timed out"
    t.join(timeout=2.0)
    return proc.returncode or 0, "".join(out_chunks), ""

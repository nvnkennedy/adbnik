"""SFTP / FTP connection helpers for the unified session model."""

import posixpath
import socket
from ftplib import FTP
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

from ..session import normalize_tcp_port

try:
    import paramiko

    try:
        import paramiko.sftp_file as _paramiko_sftp_file

        _mr = int(getattr(_paramiko_sftp_file.SFTPFile, "MAX_REQUEST_SIZE", 32768))
        _paramiko_sftp_file.SFTPFile.MAX_REQUEST_SIZE = max(_mr, 256 * 1024)
    except Exception:
        pass
except ImportError:
    paramiko = None  # type: ignore


def _set_transport_keepalive(transport: Any, interval_sec: int = 30) -> None:
    """Reduce idle TCP drops (SFTP Explorer / long sessions) on strict firewalls and NAT."""
    try:
        tr = transport
        if hasattr(tr, "get_transport"):
            tr = tr.get_transport()
        if tr is not None and hasattr(tr, "set_keepalive"):
            tr.set_keepalive(max(15, int(interval_sec)))
    except Exception:
        pass


def _close_sock(s: Optional[socket.socket]) -> None:
    if s is not None:
        try:
            s.close()
        except Exception:
            pass


def _try_sftp_over_ssh_client(
    host_s: str,
    port: int,
    uname: str,
    password: Optional[str],
    *,
    allow_agent: bool,
    look_for_keys: bool,
    timeout: int,
) -> Tuple[Optional[Any], Optional["paramiko.SFTPClient"]]:
    """Return (client, sftp) on success, (None, None) on failure."""
    if paramiko is None:
        return None, None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host_s,
            port=int(port),
            username=uname,
            password=password,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            allow_agent=allow_agent,
            look_for_keys=look_for_keys,
        )
        sftp = client.open_sftp()
        _set_transport_keepalive(client)
        return client, sftp
    except Exception:
        return None, None


def _transport_try_auth(
    t: "paramiko.Transport", uname: str, pwd: str
) -> bool:
    """Authenticate on an already-started Transport; return True if SFTP can proceed."""
    # Some appliances allow "none" auth first.
    try:
        t.auth_none(uname)
        if t.is_authenticated():
            return True
    except paramiko.AuthenticationException:
        pass
    except Exception:
        pass

    if pwd:
        try:
            t.auth_password(uname, pwd)
            if t.is_authenticated():
                return True
        except paramiko.AuthenticationException:
            pass
        except Exception:
            pass
        try:
            t.auth_interactive_dumb(uname, pwd)
            if t.is_authenticated():
                return True
        except Exception:
            pass
    else:
        # Empty password: WinSCP often succeeds via password="" or keyboard-interactive with blank fields.
        for attempt in (
            lambda: t.auth_password(uname, ""),
            lambda: t.auth_interactive_dumb(uname, ""),
        ):
            try:
                attempt()
                if t.is_authenticated():
                    return True
            except Exception:
                pass

        def _ki_handler(_title: str, _instructions: str, prompt_list: List[str]) -> List[str]:
            return [""] * len(prompt_list)

        try:
            t.auth_interactive(uname, _ki_handler)
            if t.is_authenticated():
                return True
        except Exception:
            pass

    return False


def connect_sftp(
    host: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 45,
) -> Tuple[Optional[Any], Optional["paramiko.SFTPClient"], str]:
    """Return (SSHClient or Transport, SFTPClient, error).

    Tries SSHClient auth combinations, then Transport + interactive auth. Per-attempt caps keep
    worst-case bounded while allowing slow links (satellite / high-latency SSH).
    """
    if paramiko is None:
        return None, None, "paramiko is not installed (pip install paramiko)"
    if not (host or "").strip():
        return None, None, "Host is empty"
    uname = (username or "").strip()
    if not uname:
        return None, None, "User name is required for SFTP"
    pwd = (password or "").strip()
    host_s = host.strip()
    port = normalize_tcp_port(port, 22)
    to = int(timeout or 45)
    t_try = min(45, max(12, to))
    t_tr = min(60, max(15, to))

    # --- SSHClient attempts (fewer rounds + shorter waits than legacy multi-minute worst case) ---
    client_attempts: List[Tuple[Optional[str], bool, bool]] = []
    if pwd:
        client_attempts.extend([(pwd, True, True), (pwd, False, False)])
    else:
        client_attempts.extend([(None, True, True), ("", False, False)])

    for pw, aa, lk in client_attempts:
        c, sftp = _try_sftp_over_ssh_client(
            host_s,
            port,
            uname,
            pw,
            allow_agent=aa,
            look_for_keys=lk,
            timeout=t_try,
        )
        if c is not None and sftp is not None:
            return c, sftp, ""

    # --- Transport: keyboard-interactive and empty-password paths (many headless / IVI servers) ---
    sock3: Optional[socket.socket] = None
    t: Optional["paramiko.Transport"] = None
    try:
        sock3 = socket.create_connection((host_s, int(port)), timeout=t_tr)
        sock3.settimeout(float(t_tr))
        t = paramiko.Transport(sock3)
        sock3 = None  # Transport owns the socket once created
        t.banner_timeout = t_tr
        t.auth_timeout = t_tr
        t.start_client(timeout=t_tr)
        if _transport_try_auth(t, uname, pwd):
            sftp = paramiko.SFTPClient.from_transport(t)
            if sftp is None:
                try:
                    t.close()
                except Exception:
                    pass
                return None, None, "Could not start SFTP subsystem."
            _set_transport_keepalive(t)
            return t, sftp, ""
        try:
            t.close()
        except Exception:
            pass
        return None, None, "Authentication failed (enter password or configure SSH keys in Preferences)."
    except Exception as exc:
        if t is not None:
            try:
                t.close()
            except Exception:
                pass
        else:
            _close_sock(sock3)
        return None, None, str(exc)


def sftp_listdir_attr_safe(sftp: Any, path: str) -> List[Any]:
    """Like listdir_attr, but falls back to listdir + per-file stat if the server sends modes that break paramiko/Python stat (e.g. 'mode out of range')."""
    try:
        return list(sftp.listdir_attr(path))
    except Exception:
        pass
    try:
        names = [n for n in sftp.listdir(path) if n not in (".", "..")]
    except Exception:
        return []
    base = (path or "").rstrip("/") or "/"
    out: List[Any] = []
    for n in names:
        full = posixpath.join(base, n).replace("\\", "/")
        try:
            st = sftp.stat(full)
            mode = int(getattr(st, "st_mode", 0)) & 0xFFFFFFFF
            size = int(getattr(st, "st_size", 0))
            mtime = float(getattr(st, "st_mtime", 0))
        except Exception:
            mode, size, mtime = 0o100644, 0, 0.0
        out.append(SimpleNamespace(filename=n, st_mode=mode, st_size=size, st_mtime=mtime))
    return out


def disconnect_sftp(transport: Any, sftp: Any) -> None:
    try:
        if sftp is not None:
            sftp.close()
    except Exception:
        pass
    try:
        if transport is not None:
            transport.close()
    except Exception:
        pass


def sftp_first_listable_path(sftp: Any, username: str = "") -> str:
    """Return a remote path that exists for SFTP listing (many embedded images lack /root or /home)."""
    u = (username or "").strip()
    candidates = ["/", "/tmp", "/storage", "/sdcard", "/mnt", "/media"]
    if u == "root":
        candidates.insert(0, "/root")
    if u:
        candidates.insert(1, f"/home/{u}")
    for c in candidates:
        try:
            sftp.listdir(c)
            return c
        except Exception:
            continue
    return "/"


def connect_ftp(
    host: str,
    port: int,
    user: str,
    password: str,
    timeout: int = 45,
) -> Tuple[Optional[FTP], str]:
    if not host.strip():
        return None, "Host is empty"
    port = normalize_tcp_port(port, 21)
    try:
        ftp = FTP()
        ftp.connect(host.strip(), int(port), timeout=timeout)
        ftp.login(user or "", password or "")
        ftp.set_pasv(True)
        try:
            ftp.encoding = "utf-8"
        except Exception:
            pass
        return ftp, ""
    except Exception as exc:
        return None, str(exc)


def disconnect_ftp(ftp: Optional[FTP]) -> None:
    if ftp is None:
        return
    try:
        ftp.quit()
    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

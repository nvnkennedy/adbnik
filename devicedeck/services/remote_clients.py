"""SFTP / FTP connection helpers for the unified session model."""

import socket
from ftplib import FTP, error_perm
from typing import Optional, Tuple

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore


def connect_sftp(
    host: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 25,
) -> Tuple[Optional["paramiko.Transport"], Optional["paramiko.SFTPClient"], str]:
    if paramiko is None:
        return None, None, "paramiko is not installed (pip install paramiko)"
    if not host.strip():
        return None, None, "Host is empty"
    sock = None
    try:
        sock = socket.create_connection((host.strip(), int(port)), timeout=timeout)
        t = paramiko.Transport(sock)
        t.banner_timeout = timeout
        t.auth_timeout = timeout
        uname = (username or "").strip() or None
        pwd = password if password else None
        t.connect(username=uname, password=pwd)
        sftp = paramiko.SFTPClient.from_transport(t)
        return t, sftp, ""
    except Exception as exc:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
        return None, None, str(exc)


def disconnect_sftp(transport, sftp) -> None:
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


def connect_ftp(
    host: str,
    port: int,
    user: str,
    password: str,
    timeout: int = 25,
) -> Tuple[Optional[FTP], str]:
    if not host.strip():
        return None, "Host is empty"
    try:
        ftp = FTP()
        ftp.connect(host.strip(), int(port), timeout=timeout)
        ftp.login(user or "", password or "")
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

"""Unified connection profile (WinSCP-style protocol + Moba-style session types)."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class ConnectionKind(str, Enum):
    ANDROID_ADB = "adb"
    SSH_SFTP = "ssh"  # SFTP files + ssh terminal
    FTP = "ftp"
    SERIAL = "serial"


@dataclass
class SessionProfile:
    kind: ConnectionKind
    adb_serial: str = ""
    # SSH / SFTP
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_port: int = 22
    ssh_password: str = ""
    # FTP
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    # Serial
    serial_port: str = ""
    serial_baud: str = "115200"


def normalize_tcp_port(value: object, default: int = 22) -> int:
    """Valid TCP port 1–65535; anything else (including -1 from bad config) → default."""
    try:
        p = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if 1 <= p <= 65535:
        return p
    return default


def parse_user_at_host(text: str) -> Tuple[str, str]:
    """Split user@host into (user, host). If no @, returns ("", stripped host)."""
    t = (text or "").strip()
    if not t:
        return "", ""
    if "@" in t:
        u, h = t.split("@", 1)
        return u.strip(), h.strip()
    return "", t


def ssh_command_args(profile: SessionProfile) -> list:
    """Build `ssh` argv for interactive terminal (OpenSSH client).

    `-tt` forces a PTY even when stdin is not a TTY (e.g. QProcess), avoiding
    "Pseudo-terminal will not be allocated because stdin is not a terminal."
    `StrictHostKeyChecking=accept-new` avoids blocking on first-connect host-key prompts.
    """
    host = (profile.ssh_host or "").strip()
    user = (profile.ssh_user or "").strip()
    port = normalize_tcp_port(profile.ssh_port, 22)
    common = [
        "ssh",
        "-tt",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=30",
        "-p",
        str(port),
    ]
    if not host:
        return ["ssh", "-tt"]
    target = f"{user}@{host}" if user else host
    return [*common, target]

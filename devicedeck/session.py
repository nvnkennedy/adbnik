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
    """Build `ssh` argv for interactive terminal (OpenSSH client)."""
    host = (profile.ssh_host or "").strip()
    user = (profile.ssh_user or "").strip()
    if not host:
        return ["ssh"]
    target = f"{user}@{host}" if user else host
    return ["ssh", "-p", str(int(profile.ssh_port or 22)), target]

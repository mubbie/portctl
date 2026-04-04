"""Formatting and platform utilities."""

from __future__ import annotations

import shlex
import subprocess
import sys
from typing import Optional


def normalize_process_name(name: str) -> str:
    """Lowercase and strip .exe suffix for cross-platform comparison."""
    name = name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def format_uptime(seconds: float) -> str:
    """Format seconds into a human-readable uptime string."""
    if seconds <= 0:
        return "-"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_min}m" if remaining_min else f"{hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"


def format_memory(bytes_val: int) -> str:
    """Format bytes into a human-readable memory string."""
    if bytes_val <= 0:
        return "-"
    if bytes_val < 1024:
        return f"{bytes_val} B"
    kb = bytes_val / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.1f} GB"


def format_command(cmdline: Optional[list[str]]) -> Optional[str]:
    """Join a cmdline list into a properly quoted shell string.

    Uses subprocess.list2cmdline on Windows (cmd.exe quoting)
    and shlex.join on Unix (POSIX quoting).
    """
    if not cmdline:
        return None
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmdline)
    return shlex.join(cmdline)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), timeout=5, check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode(), timeout=5, check=True)
        else:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(), timeout=5, check=True,
                )
            except FileNotFoundError:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode(), timeout=5, check=True,
                )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False

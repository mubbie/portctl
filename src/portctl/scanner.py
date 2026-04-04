"""Port scanning and process enrichment using psutil."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil

from portctl.classifier import is_dev_process
from portctl.frameworks import (
    detect_framework,
    find_project_root,
    project_name_from_root,
)
from portctl.utils import normalize_process_name


@dataclass
class ProcessInfo:
    """All known info about a process listening on a port."""

    port: int
    pid: int
    process_name: Optional[str] = None
    normalized_name: Optional[str] = None
    cmdline: Optional[list[str]] = None
    cwd: Optional[str] = None
    project_name: Optional[str] = None
    project_root: Optional[Path] = None
    framework: Optional[str] = None
    bind_address: str = ""
    bind_scope: str = ""
    uptime_seconds: float = 0
    memory_bytes: int = 0
    ppid: Optional[int] = None
    status_label: str = "healthy"
    user: Optional[str] = None
    create_time: Optional[float] = None


def bind_label(ip: str) -> str:
    """Classify a bind address: 'local' for loopback, 'public' for wildcard, or the raw IP."""
    if ip in ("127.0.0.1", "::1"):
        return "local"
    if ip in ("0.0.0.0", "::"):
        return "public"
    return ip


def _safe_proc_attr(proc: psutil.Process, attr: str, default=None):
    try:
        val = getattr(proc, attr)
        return val() if callable(val) else val
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess, OSError):
        return default


def get_process_info(pid: int, port: int, bind_ip: str) -> Optional[ProcessInfo]:
    """Build a ProcessInfo for a given PID and port."""
    if pid == 0:
        return ProcessInfo(
            port=port, pid=0, process_name="[unknown]",
            bind_address=bind_ip, bind_scope=bind_label(bind_ip),
        )

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied:
        return ProcessInfo(
            port=port, pid=pid, process_name="[access denied]",
            bind_address=bind_ip, bind_scope=bind_label(bind_ip),
        )

    name = _safe_proc_attr(proc, "name")
    cmdline = _safe_proc_attr(proc, "cmdline")
    cwd = _safe_proc_attr(proc, "cwd")
    create_time = _safe_proc_attr(proc, "create_time")
    memory_info = _safe_proc_attr(proc, "memory_info")
    ppid = _safe_proc_attr(proc, "ppid")
    proc_status = _safe_proc_attr(proc, "status")
    username = _safe_proc_attr(proc, "username")

    memory_bytes = memory_info.rss if memory_info else 0
    uptime = (time.time() - create_time) if create_time else 0

    project_root = find_project_root(cwd)
    project_name = project_name_from_root(project_root)
    framework = detect_framework(cmdline, name, project_root, port=port)

    # Status classification
    status_label = "healthy"
    if proc_status and proc_status == psutil.STATUS_ZOMBIE:
        status_label = "zombie"
    elif ppid is not None and sys.platform != "win32":
        if ppid == 1:
            status_label = "orphaned"
        elif ppid == 0:
            pass  # kernel process
        elif not psutil.pid_exists(ppid):
            status_label = "orphaned"

    norm_name = normalize_process_name(name) if name else None

    return ProcessInfo(
        port=port, pid=pid, process_name=name,
        normalized_name=norm_name,
        cmdline=cmdline, cwd=cwd,
        project_name=project_name, project_root=project_root,
        framework=framework,
        bind_address=bind_ip, bind_scope=bind_label(bind_ip),
        uptime_seconds=uptime, memory_bytes=memory_bytes,
        ppid=ppid, status_label=status_label,
        user=username, create_time=create_time,
    )


class ScanAccessDenied(Exception):
    """Raised when the OS denies access to enumerate network connections."""
    pass


@dataclass
class ScanResult:
    """Result of a port scan, including metadata about the scan itself."""
    processes: list[ProcessInfo]
    pids_missing: bool = False


def scan_ports(show_all: bool = False) -> ScanResult:
    """Scan all listening TCP ports and return enriched process info.

    Raises ScanAccessDenied if the OS blocks connection enumeration entirely.
    """
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.AccessDenied:
        raise ScanAccessDenied()

    listening = [c for c in connections if c.status == "LISTEN"]

    seen: set[tuple[int, int]] = set()
    results: list[ProcessInfo] = []
    pids_missing = False

    for conn in listening:
        port = conn.laddr.port
        pid = conn.pid
        bind_ip = conn.laddr.ip

        if pid is None:
            pids_missing = True
            pid = 0

        key = (port, pid)
        if key in seen:
            continue
        seen.add(key)

        info = get_process_info(pid, port, bind_ip)
        if info is None:
            continue

        if show_all or is_dev_process(info):
            results.append(info)

    return ScanResult(processes=results, pids_missing=pids_missing)


def get_git_branch(cwd: Optional[str]) -> Optional[str]:
    """Get the current git branch for a directory. Returns None if git is unavailable or not a repo."""
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def get_process_tree(pid: int, max_depth: int = 8) -> list[tuple[int, str]]:
    """Walk up the parent chain. Returns [(pid, name), ...] from child to root."""
    tree: list[tuple[int, str]] = []
    current_pid = pid
    for _ in range(max_depth):
        try:
            proc = psutil.Process(current_pid)
            tree.append((current_pid, proc.name()))
            parent_pid = proc.ppid()
            if parent_pid is None or parent_pid == 0 or parent_pid == current_pid:
                break
            current_pid = parent_pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            break
    return tree

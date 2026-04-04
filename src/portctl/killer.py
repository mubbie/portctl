"""Process termination logic with safety guards."""

from __future__ import annotations

from typing import Optional

import psutil

from portctl.scanner import ProcessInfo
from portctl.utils import normalize_process_name

PROTECTED_PROCESSES: set[str] = {
    "launchd", "kernel_task", "loginwindow", "windowserver",
    "systemd", "init", "sshd",
    "csrss", "wininit", "services",
    "lsass", "smss", "system",
    "explorer", "dwm",
}


def _is_protected(process_name: Optional[str]) -> bool:
    if not process_name:
        return False
    return normalize_process_name(process_name) in PROTECTED_PROCESSES


def kill_process(
    info: ProcessInfo,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[str, str]:
    """Kill a process. Accepts a ProcessInfo directly (no re-scanning).

    Returns (status, message) where status is: "killed", "skipped", "not_found", "failed", "dry_run"
    """
    if info.pid == 0:
        return ("not_found", f"Port {info.port} - no process found")

    if _is_protected(info.process_name):
        return (
            "skipped",
            f"Port {info.port} - {info.process_name} is a protected process, skipping",
        )

    label = f"{info.process_name} (PID {info.pid}) on port {info.port}"

    if dry_run:
        return ("dry_run", f"Would kill {label}")

    try:
        proc = psutil.Process(info.pid)
    except psutil.NoSuchProcess:
        return ("not_found", f"{label} - already exited")

    # Verify create_time to avoid killing a recycled PID
    if info.create_time is not None:
        try:
            if abs(proc.create_time() - info.create_time) > 1.0:
                return ("not_found", f"{label} - PID was recycled, skipping")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    try:
        proc.terminate()
    except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
        return ("failed", f"Port {info.port} - cannot kill {info.process_name}: {e}")

    try:
        proc.wait(timeout=3)
        return ("killed", f"Killed {label}")
    except psutil.TimeoutExpired:
        pass

    if force:
        try:
            proc.kill()
            proc.wait(timeout=2)
            return ("killed", f"Force killed {label}")
        except psutil.TimeoutExpired:
            return ("failed", f"Port {info.port} - {info.process_name} resisted SIGKILL")
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            return ("failed", f"Port {info.port} - cannot force kill: {e}")

    return (
        "failed",
        f"Port {info.port} - {info.process_name} did not exit after SIGTERM (try --force)",
    )

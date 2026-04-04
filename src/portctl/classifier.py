"""Signal-based dev process classification.

Uses positive signals to identify dev processes rather than maintaining
platform-specific blocklists. A process is "dev" if ANY signal fires.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portctl.scanner import ProcessInfo

from portctl.frameworks import COMMAND_FRAMEWORKS, KNOWN_RUNTIMES, is_docker_process
from portctl.utils import normalize_process_name

# Derived from COMMAND_FRAMEWORKS so there's a single source of truth
DEV_COMMAND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"\b{re.escape(kw)}\b") for kw in COMMAND_FRAMEWORKS
]


def _signal_has_project_root(proc: ProcessInfo) -> bool:
    return proc.project_root is not None


def _signal_known_runtime(proc: ProcessInfo) -> bool:
    if not proc.process_name:
        return False
    return normalize_process_name(proc.process_name) in KNOWN_RUNTIMES


def _signal_docker_process(proc: ProcessInfo) -> bool:
    return is_docker_process(proc.process_name)


def _signal_dev_command(proc: ProcessInfo) -> bool:
    if not proc.cmdline:
        return False
    cmd_lower = " ".join(proc.cmdline).lower()
    return any(pattern.search(cmd_lower) for pattern in DEV_COMMAND_PATTERNS)


def is_dev_process(proc: ProcessInfo) -> bool:
    """Returns True if ANY signal fires. Use --all to bypass."""
    return (
        _signal_has_project_root(proc)
        or _signal_known_runtime(proc)
        or _signal_docker_process(proc)
        or _signal_dev_command(proc)
    )

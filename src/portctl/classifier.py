"""Signal-based dev process classification.

Uses positive signals to identify dev processes rather than maintaining
platform-specific blocklists. A process is "dev" if ANY signal fires.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portctl.scanner import ProcessInfo

from portctl.frameworks import KNOWN_RUNTIMES, is_docker_process


def _signal_has_project_root(proc: ProcessInfo) -> bool:
    return proc.project_root is not None


def _signal_known_runtime(proc: ProcessInfo) -> bool:
    if not proc.normalized_name:
        return False
    return proc.normalized_name in KNOWN_RUNTIMES


def _signal_docker_process(proc: ProcessInfo) -> bool:
    return is_docker_process(proc.process_name)


def _signal_has_framework(proc: ProcessInfo) -> bool:
    """If detect_framework already identified a framework, it's a dev process."""
    return proc.framework is not None


def is_dev_process(proc: ProcessInfo) -> bool:
    """Returns True if ANY signal fires. Use --all to bypass."""
    return (
        _signal_has_project_root(proc)
        or _signal_known_runtime(proc)
        or _signal_docker_process(proc)
        or _signal_has_framework(proc)
    )

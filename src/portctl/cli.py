"""Typer CLI entry point for portctl."""

from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from enum import Enum
from typing import Optional

import typer
from rich.console import Console

from portctl import __version__
from portctl.display import (
    render_banner,
    render_check_result,
    render_inspect,
    render_kill_result,
    render_privilege_hint,
    render_table,
)
from portctl.killer import kill_process
from portctl.scanner import ProcessInfo, ScanAccessDenied, get_git_branch, get_process_tree, scan_ports
from portctl.utils import copy_to_clipboard, format_command

app = typer.Typer(
    name="portctl",
    help="Manage your ports.",
    add_completion=False,
    no_args_is_help=False,
)
stdout_console = Console()
stderr_console = Console(stderr=True)


class SortKey(str, Enum):
    port = "port"
    mem = "mem"
    uptime = "uptime"


SORT_FUNCTIONS: dict[str, tuple] = {
    "port": (lambda p: p.port, False),
    "mem": (lambda p: p.memory_bytes or 0, True),
    "uptime": (lambda p: p.uptime_seconds or 0, True),
}


def _matches_filter(proc: ProcessInfo, filters: list[str]) -> bool:
    if not filters:
        return True
    searchable = " ".join([
        proc.process_name or "",
        proc.framework or "",
        proc.project_name or "",
        " ".join(proc.cmdline) if proc.cmdline else "",
    ]).lower()
    return any(f.lower() in searchable for f in filters)


def _parse_port_target(s: str) -> tuple[str, int, int] | None:
    s = s.strip()
    m = re.match(r"^(\d+)-(\d+)$", s)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if 0 <= start <= end <= 65535:
            return ("range", start, end)
        return None
    try:
        port = int(s)
        if 0 <= port <= 65535:
            return ("single", port, port)
    except ValueError:
        pass
    return None


def _scan_and_build_map() -> dict[int, list[ProcessInfo]]:
    """Scan all ports once and return a port -> list of ProcessInfo map.

    Multiple processes can listen on the same port with different bind addresses.
    Exits with error if the OS denies access to enumerate connections.
    """
    try:
        result = scan_ports(show_all=True)
    except ScanAccessDenied:
        render_privilege_hint(stderr_console)
        stdout_console.print("[red]Cannot enumerate connections. Aborting.[/]")
        raise typer.Exit(1)
    if result.pids_missing:
        render_privilege_hint(stderr_console)
    port_map: dict[int, list[ProcessInfo]] = {}
    for p in result.processes:
        port_map.setdefault(p.port, []).append(p)
    return port_map


def _handle_port_target(target: str) -> None:
    parsed = _parse_port_target(target)
    if parsed is None:
        stdout_console.print(f"[red]Invalid port or range: {target}[/]")
        raise typer.Exit(1)

    kind, start, end = parsed

    with stdout_console.status("Scanning...", spinner="dots"):
        port_map = _scan_and_build_map()

    if kind == "single":
        infos = port_map.get(start)
        if not infos:
            render_check_result(stdout_console, start, None)
        else:
            info = infos[0]
            git_branch = get_git_branch(info.cwd)
            tree = get_process_tree(info.pid)
            render_inspect(stdout_console, info, git_branch, tree)
    else:
        for port in range(start, end + 1):
            infos = port_map.get(port)
            if infos:
                for info in infos:
                    stdout_console.print(
                        f"  [red]:{port}[/] {info.process_name} (PID {info.pid})"
                        + (f" [{info.framework}]" if info.framework else "")
                    )
            else:
                stdout_console.print(f"  [green]:{port}[/] free")


def _version_callback(value: bool) -> None:
    if value:
        print(f"portctl {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    all_ports: bool = typer.Option(False, "--all", "-a", help="Show all listening ports, not just dev processes"),
    sort: SortKey = typer.Option(SortKey.port, "--sort", "-s", help="Sort by: port, mem, uptime"),
    filter_terms: Optional[list[str]] = typer.Option(
        None, "--filter", "-f", help="Filter by process, framework, or project",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Limit to top N rows",
    ),
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=_version_callback, is_eager=True, help="Show version",
    ),
) -> None:
    """List listening ports, inspect a port, or scan a range.

    \b
    Examples:
      portctl              List dev server ports
      portctl 3000         Inspect port 3000 (or check availability)
      portctl 8000-9000    Scan a port range
      portctl --all        Show all listening ports
    """
    if ctx.invoked_subcommand is not None:
        return

    render_banner(stdout_console)

    with stdout_console.status("Scanning ports...", spinner="dots"):
        try:
            result = scan_ports(show_all=all_ports)
        except ScanAccessDenied:
            render_privilege_hint(stderr_console)
            stdout_console.print("[red]Cannot enumerate connections. Aborting.[/]")
            raise typer.Exit(1)
        processes = result.processes

        if result.pids_missing:
            render_privilege_hint(stderr_console)

        if filter_terms:
            processes = [p for p in processes if _matches_filter(p, filter_terms)]

        key_func, reverse = SORT_FUNCTIONS[sort.value]
        processes.sort(key=key_func, reverse=reverse)

        total = len(processes)
        if limit is not None and limit > 0:
            processes = processes[:limit]

    render_table(stdout_console, processes, total_before_limit=total if limit else None)


def _kill_all_on_port(
    infos: list[ProcessInfo], force: bool = False, dry_run: bool = False,
) -> bool:
    """Kill all listeners on a port. Returns True if all ports are free.

    "not_found" counts as success — the process already exited, so the port is free.
    """
    all_ok = True
    for info in infos:
        status, message = kill_process(info, force=force, dry_run=dry_run)
        render_kill_result(stdout_console, status, message)
        if status not in ("killed", "dry_run", "not_found"):
            all_ok = False
    return all_ok


@app.command()
def kill(
    ports: list[int] = typer.Argument(..., help="Port number(s) to kill"),
    force: bool = typer.Option(False, "--force", help="Force kill (SIGKILL)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without killing"),
) -> None:
    """Kill process(es) listening on the given port(s)."""
    with stdout_console.status("Scanning...", spinner="dots"):
        port_map = _scan_and_build_map()

    for port in ports:
        infos = port_map.get(port)
        if not infos:
            render_kill_result(stdout_console, "not_found", f"Port {port} - no process found")
            continue
        _kill_all_on_port(infos, force=force, dry_run=dry_run)


@app.command()
def free(
    ports: list[int] = typer.Argument(..., help="Port(s) to free"),
) -> None:
    """Free port(s) by killing their processes, then optionally run a command.

    \b
    Usage: portctl free 3000 -- npm start
    """
    remaining = _get_remaining_args()

    with stdout_console.status("Scanning...", spinner="dots"):
        port_map = _scan_and_build_map()

    all_freed = True
    for port in ports:
        infos = port_map.get(port)
        if not infos:
            stdout_console.print(f"  [dim]Port {port} is already free[/]")
            continue
        if not _kill_all_on_port(infos):
            all_freed = False

    if remaining:
        if not all_freed:
            stdout_console.print("[yellow]  Not all ports were freed. Skipping command.[/]")
        else:
            cmd_display = format_command(remaining) or " ".join(remaining)
            stdout_console.print(f"  [dim]Running: {cmd_display}[/]")
            result = subprocess.run(remaining)
            if result.returncode != 0:
                stdout_console.print(f"  [yellow]Command exited with code {result.returncode}[/]")


@app.command()
def cmd(
    port: int = typer.Argument(..., help="Port number"),
    copy: bool = typer.Option(False, "--copy", help="Copy command to clipboard"),
) -> None:
    """Show the startup command for a port's process."""
    with stdout_console.status("Scanning...", spinner="dots"):
        port_map = _scan_and_build_map()
        infos = port_map.get(port)

    if not infos:
        stdout_console.print(f"[dim]No process found on port {port}.[/]")
        raise typer.Exit(1)

    info = infos[0]
    command = format_command(info.cmdline)
    if not command:
        stdout_console.print(f"[dim]Could not read command for PID {info.pid}.[/]")
        raise typer.Exit(1)

    stdout_console.print(command)

    if copy:
        if copy_to_clipboard(command):
            stdout_console.print("[dim]Copied to clipboard.[/]")
        else:
            stdout_console.print("[yellow]Clipboard not available.[/]")


@app.command(name="open")
def open_port(
    port: int = typer.Argument(..., help="Port number to open in browser"),
) -> None:
    """Open localhost:<port> in the default browser."""
    url = f"http://localhost:{port}"
    webbrowser.open(url)
    stdout_console.print(f"  Opened {url}")


@app.command(name="copy")
def copy_url(
    port: int = typer.Argument(..., help="Port number"),
) -> None:
    """Copy localhost:<port> URL to clipboard."""
    url = f"http://localhost:{port}"
    if copy_to_clipboard(url):
        stdout_console.print(f"  Copied {url}")
    else:
        stdout_console.print(f"  {url}")
        stdout_console.print("  [yellow]Clipboard not available.[/]")


@app.command()
def clean(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without killing"),
) -> None:
    """Kill orphaned and zombie dev processes."""
    with stdout_console.status("Scanning...", spinner="dots"):
        try:
            result = scan_ports(show_all=False)
        except ScanAccessDenied:
            render_privilege_hint(stderr_console)
            stdout_console.print("[red]Cannot enumerate connections. Aborting.[/]")
            raise typer.Exit(1)
        targets = [p for p in result.processes if p.status_label in ("orphaned", "zombie")]

    if not targets:
        stdout_console.print("[dim]No orphaned or zombie processes found.[/]")
        return

    for info in targets:
        status, message = kill_process(info, force=False, dry_run=dry_run)
        render_kill_result(stdout_console, status, message)


def _get_remaining_args() -> list[str]:
    return _trailing_command


_SUBCOMMANDS = {"kill", "free", "cmd", "open", "copy", "clean", "--help", "-h", "--version", "-v"}

# Stores args after "--" stripped before typer parses (for `free` command)
_trailing_command: list[str] = []


def _cli_entry() -> None:
    """Entry point — intercept port/range args and strip trailing commands before typer parses."""
    global _trailing_command

    # Strip everything after "--" so typer doesn't choke on non-integer args
    # (e.g. "portctl free 3000 -- npm start")
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        _trailing_command = sys.argv[idx + 1:]
        sys.argv = sys.argv[:idx]
    else:
        _trailing_command = []

    args = sys.argv[1:]
    if args:
        first = args[0]
        if first not in _SUBCOMMANDS and not first.startswith("-"):
            # If it looks like a port/range (digits, maybe a dash), handle it
            if re.match(r"^\d+(-\d+)?$", first):
                parsed = _parse_port_target(first)
                if parsed is not None:
                    _handle_port_target(first)
                    return
                # Looks like a port/range but invalid — show a clear error
                stdout_console.print(f"[red]Invalid port or range: {first}[/]")
                raise SystemExit(1)
    app()


if __name__ == "__main__":
    _cli_entry()

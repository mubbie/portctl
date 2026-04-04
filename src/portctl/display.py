"""Rich TUI rendering — tables, panels, detail views."""

from __future__ import annotations

import sys
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from portctl.scanner import ProcessInfo
from portctl.utils import format_command, format_memory, format_uptime

# ASCII-safe symbols for Windows legacy consoles
_USE_ASCII = sys.platform == "win32" and not (sys.stdout.encoding or "").lower().startswith("utf")
_BULLET = "*" if _USE_ASCII else "\u25cf"
_DASH = "-" if _USE_ASCII else "\u2014"
_CHECK = "+" if _USE_ASCII else "\u2713"
_CROSS = "x" if _USE_ASCII else "\u2717"
_WARN = "!" if _USE_ASCII else "\u26a0"
_DOT = "." if _USE_ASCII else "\u00b7"

FRAMEWORK_STYLES: dict[str, str] = {
    "Next.js": "bold white",
    "Vite": "yellow",
    "React": "cyan",
    "Vue": "green",
    "Angular": "red",
    "Svelte": "rgb(255,62,0)",
    "Express": "dim",
    "Django": "green",
    "Flask": "white",
    "FastAPI": "cyan",
    "Rails": "red",
    "Go": "cyan",
    "Rust": "rgb(222,165,93)",
    "Python": "yellow",
    "Node.js": "green",
    "Docker": "blue",
    "Bun": "white",
    "Deno": "white",
    "Gunicorn": "green",
    "Fastify": "white",
    "Koa": "white",
    "Hapi": "yellow",
    "Nuxt": "green",
    "Remix": "white",
    "Astro": "rgb(255,93,0)",
    "Gatsby": "magenta",
    "Webpack": "cyan",
    "PHP": "blue",
    ".NET": "magenta",
    "Elixir": "magenta",
    "Erlang": "red",
}

STATUS_MARKUP: dict[str, str] = {
    "healthy": f"[green]{_BULLET} healthy[/]",
    "orphaned": f"[yellow]{_BULLET} orphaned[/]",
    "zombie": f"[red]{_BULLET} zombie[/]",
}


def _styled_framework(name: Optional[str]) -> str:
    if not name:
        return f"[dim]{_DASH}[/]"
    style = FRAMEWORK_STYLES.get(name)
    if not style:
        base = name.split("(")[0].strip() if "(" in name else name
        style = FRAMEWORK_STYLES.get(base, "white")
    return f"[{style}]{name}[/]"


def _styled_bind(scope: str) -> str:
    if scope == "local":
        return "[dim green]local[/]"
    if scope == "public":
        return "[yellow]public[/]"
    return f"[dim]{scope}[/]"


def render_banner(console: Console) -> None:
    console.print(
        Panel(
            "[bold]portctl[/]\n[dim]manage your ports[/]",
            border_style="cyan",
            width=44,
        )
    )


def render_privilege_hint(console: Console) -> None:
    """Print a platform-specific hint about needing elevated privileges."""
    if sys.platform == "win32":
        console.print("[yellow]! Run as Administrator for full process details.[/]")
    elif sys.platform == "darwin":
        console.print("[yellow]! Run with sudo for full visibility across all users.[/]")
    else:
        console.print("[yellow]! Run with sudo for full visibility.[/]")


def render_table(
    console: Console,
    processes: list[ProcessInfo],
    total_before_limit: Optional[int] = None,
) -> None:
    if not processes:
        console.print("[dim]No listening ports found.[/]")
        return

    has_project = any(p.project_name for p in processes)
    has_framework = any(p.framework for p in processes)

    table = Table(box=box.ROUNDED, border_style="dim", header_style="bold cyan")
    table.add_column("PORT", justify="right", style="bold", no_wrap=True)
    table.add_column("PROCESS", no_wrap=True)
    table.add_column("PID", justify="right", style="dim", no_wrap=True)
    if has_project:
        table.add_column("PROJECT", no_wrap=True)
    if has_framework:
        table.add_column("FRAMEWORK", no_wrap=True)
    table.add_column("UPTIME", justify="right", no_wrap=True)
    table.add_column("MEM", justify="right", no_wrap=True)
    table.add_column("BIND", no_wrap=True)
    table.add_column("STATUS", no_wrap=True)

    for p in processes:
        row: list[str] = [
            str(p.port),
            p.process_name or f"[dim]{_DASH}[/]",
            str(p.pid),
        ]
        if has_project:
            row.append(p.project_name or f"[dim]{_DASH}[/]")
        if has_framework:
            row.append(_styled_framework(p.framework))
        row.extend([
            format_uptime(p.uptime_seconds),
            format_memory(p.memory_bytes),
            _styled_bind(p.bind_scope),
            STATUS_MARKUP.get(p.status_label, p.status_label),
        ])
        table.add_row(*row)

    console.print(table)

    if total_before_limit is not None and total_before_limit > len(processes):
        console.print(
            f"[dim]Showing {len(processes)} of {total_before_limit} ports "
            f"{_DOT} remove -n to see all[/]"
        )


def render_inspect(
    console: Console,
    info: ProcessInfo,
    git_branch: str | None,
    process_tree: list[tuple[int, str]],
) -> None:
    from datetime import datetime

    d = _DASH
    started = d
    if info.create_time:
        started = datetime.fromtimestamp(info.create_time).strftime("%Y-%m-%d %H:%M:%S")

    cmd_str = format_command(info.cmdline) or d

    lines = [
        f"[bold]Process[/]     {info.process_name or d}",
        f"[bold]PID[/]         {info.pid}",
        f"[bold]Status[/]      {STATUS_MARKUP.get(info.status_label, info.status_label)}",
        f"[bold]Framework[/]   {_styled_framework(info.framework)}",
        f"[bold]Memory[/]      {format_memory(info.memory_bytes)}",
        f"[bold]Uptime[/]      {format_uptime(info.uptime_seconds)}",
        f"[bold]Started[/]     {started}",
        f"[bold]Bind[/]        {_styled_bind(info.bind_scope)} [dim]({info.bind_address})[/]",
        f"[bold]Command[/]     {cmd_str}",
    ]

    lines.append("")
    lines.append(f"[bold]Directory[/]   {info.cwd or d}")
    lines.append(f"[bold]Project[/]     {info.project_name or d}")
    lines.append(f"[bold]Git Branch[/]  {git_branch or d}")

    if process_tree:
        lines.append("")
        lines.append("[bold]Process Tree[/]")
        for i, (pid, name) in enumerate(process_tree):
            arrow = "->" if _USE_ASCII else "\u2192"
            branch = "+-" if _USE_ASCII else "\u2514\u2500"
            prefix = arrow if i == 0 else f"{'  ' * (i - 1)}  {branch}"
            lines.append(f"  {prefix} {name} ({pid})")

    console.print(Panel(
        "\n".join(lines),
        title=f"Port :{info.port}",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    ))


def render_check_result(console: Console, port: int, info: ProcessInfo | None) -> None:
    if info is None:
        console.print(f"  [green]{_CHECK}[/] Port {port} is available")
    else:
        console.print(f"  [red]{_CROSS}[/] Port {port} is in use")
        console.print(f"    Process: {info.process_name} (PID {info.pid})")
        if info.project_name:
            console.print(f"    Project: {info.project_name}")
        if info.framework:
            console.print(f"    Framework: {info.framework}")
        console.print(f"    Uptime: {format_uptime(info.uptime_seconds)}")
        console.print(f"    Run [bold]portctl kill {port}[/] to free it")


def render_kill_result(console: Console, status: str, message: str) -> None:
    icons = {
        "killed": f"[green]{_CHECK}[/]",
        "dry_run": "[cyan]~[/]",
        "skipped": f"[yellow]{_WARN}[/]",
        "not_found": f"[red]{_CROSS}[/]",
        "failed": f"[red]{_CROSS}[/]",
    }
    icon = icons.get(status, " ")
    console.print(f"  {icon} {message}")

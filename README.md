# portctl

> Manage your ports.

A cross-platform Python CLI tool for viewing, managing, and killing processes on TCP ports.

Inspired by [port-whisperer](https://github.com/LarsenCundric/port-whisperer) by [Larsen Cundric](https://x.com/larsencc).

## Install

```bash
pip install portctl
# or
pipx install portctl
```

## Quick Start

```bash
portctl                    # Show dev server ports
portctl 3000               # Inspect what's on port 3000
portctl kill 3000           # Kill it
```

## Commands

### List ports

```bash
portctl                    # Dev server ports only
portctl --all              # All listening ports
portctl --sort mem         # Sort by memory (also: uptime)
portctl -f django          # Filter by process, framework, or project
portctl -n 5               # Limit to top N rows
```

### Inspect a port

```bash
portctl 3000               # Detail view if occupied, "available" if free
```

Shows process info, framework, memory, uptime, bind address, working directory, git branch, and process tree.

### Scan a range

```bash
portctl 8000-9000          # Show which ports are in use
```

### Kill processes

```bash
portctl kill 3000          # Kill process on port 3000
portctl kill 3000 8080     # Kill multiple ports
portctl kill 3000 --force  # Force kill (SIGKILL)
portctl kill 3000 --dry-run  # Preview without killing
```

### Free a port and run a command

```bash
portctl free 3000 -- npm start      # Kill port 3000, then run npm start
portctl free 3000 5432 -- docker compose up  # Free multiple, then run
```

### Show startup command

```bash
portctl cmd 3000           # Print the command that started the process
portctl cmd 3000 --copy    # Copy it to clipboard
```

### Utilities

```bash
portctl open 3000          # Open http://localhost:3000 in browser
portctl copy 3000          # Copy http://localhost:3000 to clipboard
portctl clean              # Kill orphaned/zombie dev processes
portctl clean --dry-run    # Preview without killing
```

## Features

- **Cross-platform** -- works on macOS, Linux, and Windows
- **Framework detection** -- identifies Next.js, Vite, Django, FastAPI, Flask, Express, and 20+ others
- **Project detection** -- finds project root and name from package.json, pyproject.toml, Cargo.toml, etc.
- **Smart filtering** -- shows only dev processes by default, use `--all` for everything
- **Protected processes** -- refuses to kill system-critical processes (systemd, lsass, etc.)
- **Git branch** -- shows which branch each process is running from

## Platform Support

| Platform | Status |
|----------|--------|
| macOS    | Supported (use `sudo` for full visibility) |
| Linux    | Supported |
| Windows  | Supported (admin recommended for full PID visibility) |

## License

MIT

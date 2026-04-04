# portctl

> Manage your ports.

A cross-platform Python CLI tool for viewing, managing, and killing processes on TCP ports.

Inspired by [port-whisperer](https://github.com/LarsenCundric/port-whisperer) by [Larsen Cundric](https://x.com/larsencc).

## What it looks like

```
$ portctl

 ┌──────────────────────────────────────────┐
 │ portctl                                  │
 │ scanning your ports...                   │
 └──────────────────────────────────────────┘

  PORT    PROCESS      PID     PROJECT       FRAMEWORK      UPTIME   MEM        BIND     STATUS
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  :8000   python.exe   14320   payments-api  FastAPI        3h 12m   48.7 MB   public   ● healthy
  :5173   node         52981   dashboard     Vite           22m      112.4 MB  local    ● healthy
  :8080   go           8734    gateway       Go             6d 1h    23.1 MB   public   ● healthy
  :5432   docker       7712    —             Docker (PG)    14d 8h   67.0 MB   local    ● healthy

  4 ports active  ·  Run portctl <port> for details  ·  --all to show everything
```

```
$ portctl 5173

 ┌─────────────────────── Port :5173 ───────────────────────┐
 │                                                          │
 │  Process     node                                        │
 │  PID         52981                                       │
 │  Status      ● healthy                                   │
 │  Framework   Vite                                        │
 │  Memory      112.4 MB                                    │
 │  Uptime      22m                                         │
 │  Started     2026-04-04 10:15:42                         │
 │  Bind        local (127.0.0.1)                           │
 │  Command     node node_modules/.bin/vite --port 5173     │
 │                                                          │
 │  Directory   /home/mubarak/projects/dashboard            │
 │  Project     dashboard                                   │
 │  Git Branch  feat/charts                                 │
 │                                                          │
 │  Process Tree                                            │
 │    → node (52981)                                        │
 │      └─ bash (52900)                                     │
 │        └─ tmux: server (1120)                            │
 │                                                          │
 └──────────────────────────────────────────────────────────┘

  Run portctl kill 5173 to stop  ·  portctl cmd 5173 to see startup command
```

```
$ portctl 8000-8100

  :8000 python.exe (PID 14320) [FastAPI]
  :8001 free
  :8002 free
  ...
  :8080 go (PID 8734) [Go]
  :8081 free
  ...
  :8100 free
```

```
$ portctl free 5173 -- npm run dev

  ✓ Killed node (PID 52981) on port 5173
  Running: npm run dev
```

```
$ portctl kill 8000 8080

  ✓ Killed python.exe (PID 14320) on port 8000
  ✓ Killed go (PID 8734) on port 8080
```

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

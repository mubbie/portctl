# portctl

> Manage your ports.

A cross-platform Python CLI tool for viewing, managing, and killing processes on TCP ports.

Inspired by [port-whisperer](https://github.com/LarsenCundric/port-whisperer) by [Larsen Cundric](https://x.com/larsencc).

## Install

```bash
pip install portctl
```

## Usage

```bash
portctl                    # Show dev server ports
portctl --all              # Show all listening ports
portctl kill 3000          # Kill process on port 3000
```

## Platform Support

| Platform | Status |
|----------|--------|
| macOS    | Supported |
| Linux    | Supported |
| Windows  | Supported (admin recommended for full PID visibility) |

## License

MIT

"""Framework and project detection rules."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from portctl.utils import normalize_process_name

# --- Project root detection ---

PROJECT_MARKERS = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "mix.exs",
    "composer.json",
    ".git",
]

MAX_WALK_DEPTH = 15


@lru_cache(maxsize=256)
def find_project_root(cwd: Optional[str]) -> Optional[Path]:
    """Walk up from cwd looking for a project marker. Cached by cwd string."""
    if not cwd:
        return None
    path = Path(cwd).resolve()
    for _ in range(MAX_WALK_DEPTH):
        for marker in PROJECT_MARKERS:
            if (path / marker).exists():
                return path
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None


def project_name_from_root(root: Optional[Path]) -> Optional[str]:
    if root is None:
        return None
    return root.name


# --- Docker detection (single source of truth) ---

DOCKER_NAMES: set[str] = {
    "docker", "docker-sandbox", "docker-proxy", "com.docker.backend",
}
DOCKER_PREFIX = "com.docker"


def is_docker_process(process_name: Optional[str]) -> bool:
    if not process_name:
        return False
    name = normalize_process_name(process_name)
    return name in DOCKER_NAMES or name.startswith(DOCKER_PREFIX)


# Well-known port -> service name (for Docker-proxied ports)
WELL_KNOWN_PORTS: dict[int, str] = {
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
    9200: "Elasticsearch",
    9092: "Kafka",
    5672: "RabbitMQ",
    15672: "RabbitMQ",
    8500: "Consul",
    2181: "ZooKeeper",
    11211: "Memcached",
    80: "nginx",
    443: "nginx",
    8080: "nginx",
}


# --- Framework detection ---

# Layer 1: command line keywords -> framework name
COMMAND_FRAMEWORKS: dict[str, str] = {
    "next": "Next.js",
    "vite": "Vite",
    "nuxt": "Nuxt",
    "angular": "Angular",
    "ng": "Angular",
    "webpack": "Webpack",
    "remix": "Remix",
    "astro": "Astro",
    "gatsby": "Gatsby",
    "flask": "Flask",
    "django": "Django",
    "manage.py": "Django",
    "uvicorn": "FastAPI",
    "gunicorn": "Gunicorn",
    "rails": "Rails",
    "cargo": "Rust",
    "rustc": "Rust",
}

# Layer 3: process name -> framework (also the source of truth for known runtimes)
PROCESS_FRAMEWORKS: dict[str, str] = {
    "node": "Node.js",
    "python": "Python",
    "python3": "Python",
    "ruby": "Ruby",
    "java": "Java",
    "go": "Go",
    "deno": "Deno",
    "bun": "Bun",
    "php": "PHP",
    "dotnet": ".NET",
    "elixir": "Elixir",
    "erlang": "Erlang",
}

# Derived: set of known runtime names (used by classifier)
KNOWN_RUNTIMES: set[str] = set(PROCESS_FRAMEWORKS.keys())

# Compiled word-boundary patterns for command-line matching (shared with classifier)
COMMAND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE), fw)
    for kw, fw in COMMAND_FRAMEWORKS.items()
]

# Layer 2: config files that indicate a framework
CONFIG_FILE_FRAMEWORKS: dict[str, str] = {
    "next.config.js": "Next.js",
    "next.config.mjs": "Next.js",
    "next.config.ts": "Next.js",
    "vite.config.js": "Vite",
    "vite.config.ts": "Vite",
    "vite.config.mjs": "Vite",
    "angular.json": "Angular",
    "nuxt.config.js": "Nuxt",
    "nuxt.config.ts": "Nuxt",
    "remix.config.js": "Remix",
    "astro.config.mjs": "Astro",
    "gatsby-config.js": "Gatsby",
    "svelte.config.js": "Svelte",
    "manage.py": "Django",
}

# package.json dependency -> framework (checked in order, first match wins)
PACKAGE_JSON_FRAMEWORKS: list[tuple[str, str]] = [
    ("next", "Next.js"),
    ("nuxt", "Nuxt"),
    ("@angular/core", "Angular"),
    ("svelte", "Svelte"),
    ("remix", "Remix"),
    ("astro", "Astro"),
    ("gatsby", "Gatsby"),
    ("vite", "Vite"),
    ("vue", "Vue"),
    ("react", "React"),
    ("express", "Express"),
    ("fastify", "Fastify"),
    ("koa", "Koa"),
    ("hapi", "Hapi"),
]


# pyproject.toml dependency keywords -> framework (substring match on file content)
PYPROJECT_FRAMEWORKS: list[tuple[str, str]] = [
    ("fastapi", "FastAPI"),
    ("django", "Django"),
    ("flask", "Flask"),
    ("starlette", "Starlette"),
    ("tornado", "Tornado"),
    ("sanic", "Sanic"),
    ("aiohttp", "aiohttp"),
]


@lru_cache(maxsize=128)
def _detect_from_project(project_root_str: str) -> Optional[str]:
    """Detect framework from project files. Cached by project root path."""
    project_root = Path(project_root_str)

    for config_file, framework in CONFIG_FILE_FRAMEWORKS.items():
        if (project_root / config_file).exists():
            return framework

    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            all_deps: dict[str, str] = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            for dep_name, framework in PACKAGE_JSON_FRAMEWORKS:
                if dep_name in all_deps:
                    return framework
        except (json.JSONDecodeError, OSError):
            pass

    # Python projects: check pyproject.toml dependencies for known frameworks
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            for keyword, framework in PYPROJECT_FRAMEWORKS:
                if keyword in content:
                    return framework
        except OSError:
            pass

    return None


def detect_framework(
    cmdline: Optional[list[str]],
    process_name: Optional[str],
    project_root: Optional[Path],
    port: Optional[int] = None,
) -> Optional[str]:
    """Detect framework using layers in priority order."""
    # Docker detection
    if is_docker_process(process_name):
        if port and port in WELL_KNOWN_PORTS:
            return f"Docker ({WELL_KNOWN_PORTS[port]})"
        return "Docker"

    # Layer 1: command line keywords (word-boundary regex)
    if cmdline:
        cmd_str = " ".join(cmdline)
        for pattern, framework in COMMAND_PATTERNS:
            if pattern.search(cmd_str):
                return framework

    # Layer 2: project files (cached per project root)
    if project_root:
        result = _detect_from_project(str(project_root))
        if result:
            return result

    # Layer 3: process name fallback
    if process_name:
        name = normalize_process_name(process_name)
        result = PROCESS_FRAMEWORKS.get(name)
        if result:
            return result

    return None

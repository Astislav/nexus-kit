import re
import sys
from importlib.metadata import version
from pathlib import Path


_TEMPLATES: dict[str, str] = {
    "main.py": """\
import faulthandler
import sys

from app.application import Application
from app.config.di import DI_CONFIG
from app.config.environment import Environment
from nexus_kit import Root
from nexus_kit.impl import ContainerInjector

if __name__ == "__main__":
    if sys.stderr is not None:  # windowed builds (console=False) have no stderr
        faulthandler.enable(all_threads=True)

    env = Environment(Root.external(".env"))
    container = ContainerInjector(DI_CONFIG)
    container.set(Environment, env)
    Application(env, container).run()
""",
    "pyproject.toml": """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{APP_NAME}}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "nexus-kit~={{NEXUS_REF}}",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]
""",
    ".gitignore": """\
.venv/
__pycache__/
*.pyc
.env
dist/
build/
.pytest_cache/
.ruff_cache/
.idea/
""",
    ".env": """\
APP_NAME={{APP_NAME}}
TICK_SECONDS=0.7
RUN_SECONDS=3
""",
    ".env.example": """\
# Template for the real .env (which is gitignored and never ships by default).
# On a target machine: copy next to the executable as `.env` and fill in.
APP_NAME={{APP_NAME}}
TICK_SECONDS=0.7
RUN_SECONDS=3
""",
    "app/__init__.py": "",
    "app/application.py": """\
import time

from nexus_kit.impl import ServiceRunner
from nexus_kit.interfaces import ApplicationInterface, ContainerInterface

from app.config.environment import Environment
from app.services.ticker import Ticker


class Application(ApplicationInterface):
    SERVICES = [Ticker]  # startup order; stopped in reverse on any exit

    def __init__(self, environment: Environment, container: ContainerInterface) -> None:
        self._env = environment
        self._container = container

    def run(self) -> None:
        with ServiceRunner(self._container, self.SERVICES):
            print(f"[{self._env.APP_NAME}] running for {self._env.RUN_SECONDS}s — Ctrl+C to stop early")
            try:
                # Replace with your main loop: server.wait(), app.exec(), game loop
                time.sleep(self._env.RUN_SECONDS)
            except KeyboardInterrupt:
                pass
        # leaving the block stopped the ticker and joined its thread — nothing orphaned
""",
    "app/config/__init__.py": "",
    "app/config/di.py": """\
# Register your swappable seams here: {Interface: Implementation}
from app.services.console_reporter import ConsoleReporter
from app.services.reporter_interface import ReporterInterface

DI_CONFIG = {
    ReporterInterface: ConsoleReporter,
}
""",
    "app/config/environment.py": """\
from pathlib import Path

from injector import singleton

from nexus_kit.interfaces import EnvironmentInterface


@singleton
class Environment(EnvironmentInterface):
    # Add your config fields here — they are read from .env automatically
    APP_NAME: str = "{{APP_NAME}}"
    TICK_SECONDS: float = 0.7
    RUN_SECONDS: float = 3.0

    def __init__(self, env_path: Path) -> None:
        super().__init__(_env_file=env_path)
""",
    "app/services/__init__.py": "",
    "app/services/ticker.py": """\
import threading

from injector import inject, singleton

from nexus_kit.interfaces import ServiceInterface

from app.config.environment import Environment
from app.services.reporter_interface import ReporterInterface


# The worker-thread skeleton every long-lived app ends up hand-rolling:
# stop Event + bounded join. Swap the loop body for your poller, device
# monitor or queue drainer. Not in DI_CONFIG: a concrete @singleton
# service resolves itself; its dependencies arrive via @inject.
@singleton
class Ticker(ServiceInterface):
    @inject
    def __init__(self, env: Environment, reporter: ReporterInterface) -> None:
        self._interval = env.TICK_SECONDS
        self._reporter = reporter
        self._ticks = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        print(f"[ticker] started (every {self._interval}s)")
        self._thread = threading.Thread(target=self._run, name="ticker", daemon=True)
        self._thread.start()

    def stop(self) -> None:  # must be idempotent
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
            print(f"[ticker] stopped after {self._ticks} ticks")

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            self._ticks += 1
            self._reporter.report(self._ticks)
""",
    "app/services/reporter_interface.py": """\
from abc import ABC, abstractmethod


class ReporterInterface(ABC):
    @abstractmethod
    def report(self, tick: int) -> None: ...
""",
    "app/services/console_reporter.py": """\
from injector import singleton

from app.services.reporter_interface import ReporterInterface


@singleton
class ConsoleReporter(ReporterInterface):
    def report(self, tick: int) -> None:
        print(f"tick #{tick}")
""",
    "CLAUDE.md": """\
# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

This app is built on the **nexus-kit** framework. The framework's API, the bootstrap
pattern and the gotchas live in the guides under `.ai/` — read them before touching DI,
config or the composition root (`app/config/di.py`). Every installed nexus-kit package
maintains its own guide there: after adding, upgrading or removing one, run
`uv run nexus-kit sync-ai` (trust a satellite once with `--trust <pkg>`; the kernel is
trusted implicitly). Keep this file thin: put engineering discipline in `.ai/` and only
repo-specific facts here.
""",
    ".ai/nexus-kit.md": """\
<!-- nexus-kit sync-ai: nexus-kit {{NEXUS_REF}} — generated; refresh with `nexus-kit sync-ai`, do not edit by hand -->
# nexus-kit — quick reference (how to build an app on this framework)

Compact cheat-sheet for the **nexus-kit** framework (PyPI `nexus-kit`, import
`nexus_kit`; github.com/Astislav/nexus), pinned to **~={{NEXUS_REF}}**. For depth: the
framework's own `.ai/guide.md`, or the installed source at
`.venv/Lib/site-packages/nexus_kit/`.

## What it is

A tiny application bootstrap: a **DI container** (wraps `injector`) + a **config base**
(wraps `pydantic-settings`) + **logging** + **`Root`** (paths) + the `nexus-kit new` CLI.
No domain, HTTP or DB.

## Public API

| Symbol | Import | Role |
|---|---|---|
| `ApplicationInterface` | `nexus_kit.interfaces` | run contract: `__init__(env, container)` + `run()` |
| `ContainerInterface` | `nexus_kit.interfaces` | DI contract: `get(cls)`, `set(cls, value)` |
| `EnvironmentInterface` | `nexus_kit.interfaces` | typed config base (pydantic BaseSettings + `@singleton`) |
| `ServiceInterface` | `nexus_kit.interfaces` | long-lived service: `start()`/`stop()` (sync or async, `stop()` idempotent) |
| `Root` | `nexus_kit` | paths: `Root.internal(*p)` (bundled assets) / `Root.external(*p)` (files next to the executable — or next to `main.py` in dev: `.env`, db) |
| `ContainerInjector` | `nexus_kit.impl` | concrete container; constructor takes `DI_CONFIG: dict[Type, Impl]` |
| `ServiceRunner` | `nexus_kit.impl` | ordered start / guaranteed reverse-order stop: `with`/`async with ServiceRunner(container, SERVICES)` around the app body |
| `NamedLogger` / `StdoutHandler` / `LogFormatter` | `nexus_kit.logging` | DI-injectable logging |

**Gotcha:** `@singleton`, `@inject`, `Injector` come from the `injector` package, NOT
from nexus-kit (`from injector import inject, singleton`). Nexus never re-exports them.

**Dependencies:** `injector` and `pydantic-settings` are core dependencies of nexus —
no extras, everything works out of the box.

## Bootstrap (`main.py`)

```python
env = Environment(Root.external(".env"))   # 1. config
container = ContainerInjector(DI_CONFIG)   # 2. wiring
container.set(Environment, env)            # 3. env is NOT auto-bound — bind it by hand
Application(env, container).run()          # 4. start
```

- `DI_CONFIG` (composition root) is a `dict{Interface: Impl}`; register only swappable
  seams — `@singleton @inject` services are built by the container from their constructors.
- **Do not bind a class to itself.** Interfaces carry the `Interface` suffix; implementations don't.
- Long-lived services are `@singleton`, dependencies come via an `@inject` constructor.
- Logging: subclass `NamedLogger` (class attr `name`), inject by type; change the format
  by rebinding `LogFormatter` in `DI_CONFIG`.

## Lifecycle (`ServiceRunner`)

Long-lived services implement `ServiceInterface` — `start()`/`stop()`, sync or async,
`stop()` must be idempotent. `Application` lists them in `SERVICES` (startup order) and
wraps the app body in the runner; see `app/services/ticker.py` for the pattern
(worker thread + stop Event + bounded join):

```python
class Application(ApplicationInterface):
    SERVICES = [Database, Poller, HttpApiService]      # startup order

    def run(self) -> None:
        with ServiceRunner(self._container, self.SERVICES):   # async app: `async with`
            self._main_loop()
        # leaving the block stops everything in reverse — on return, exception, Ctrl+C
```

Guarantees: crash-safe startup (a failed `start()` still gets its own best-effort
`stop()`, then the already-started services roll back — write `stop()` to tolerate
partially initialized state); a failing `stop()` is logged, teardown continues; async
stops are bounded by `stop_grace` (default 10s), sync stops run inline unbounded;
`stop()` must be idempotent. The runner never grabs
signals — the exit is triggered by uvicorn / Qt `aboutToQuit` / your own code. Services
do NOT go into `DI_CONFIG` (concrete `@singleton` classes resolve themselves).

## Freezing (PyInstaller)

`nexus-kit freeze` (once, from the app root) generates `app.spec` and fixes
`.gitignore` (`app.spec` is source — commit it). `nexus-kit build` (every release,
any platform) clean-builds `dist/` from the spec. Two resource classes mirror
`Root`: BUNDLED data is listed in `app.spec`, read via `Root.internal(...)`;
EXTERNAL files are copied next to the binary by `build` (`resources/`,
`.env.example`), read via `Root.external(...)`. The real `.env` ships ONLY with
`nexus-kit build --env`. For reproducible builds: `uv add --dev pyinstaller`.
Frozen targets need Windows 10+ or any modern linux/macos (Python 3.12 floor).

## Satellites (nexus-kit-* packages)

The kernel stays thin; integrations live in satellite packages (`nexus-kit-fastapi`,
...). Every satellite ships its own AI guide inside its wheel. After `uv add`,
upgrade or removal of ANY nexus-kit package, run **`uv run nexus-kit sync-ai`** from
the app root (via `uv run` so the project environment is the one scanned): it mirrors
each installed, trusted `nexus-kit-*` package's guide into `.ai/<dist-name>.md` and
refreshes this file, pinned to the kernel version installed in the app.

A guide is instructions an AI assistant will follow, so a satellite is mirrored only
after you trust it once: `uv run nexus-kit sync-ai --trust nexus-kit-fastapi` (the
kernel is trusted implicitly; the trust list lives in `.ai/trusted-guides.txt`).
Managed files carry the header stamp above; your own `.ai/*.md` files are never
touched. A plain run only creates/updates and quarantines the guide of any package
that is uninstalled or no longer trusted (moved to `<name>.md.untrusted`, out of the
files you read); `--prune` deletes those instead.

## What nexus does NOT provide (you hand-roll these)

Signal handling (`ServiceRunner` never grabs SIGINT/SIGTERM — exit is triggered by
uvicorn, Qt `aboutToQuit`, or your own code); a background-service/worker base;
a repository/DB layer; a test harness; HTTP/routing/retries.
""",
}


# --- freeze: PyInstaller packaging artifacts, generated into an existing app ---

_FREEZE_TEMPLATES: dict[str, str] = {
    "app.spec": '''\
# PyInstaller build spec for {{APP_NAME}} — generated by `nexus-kit freeze`.
#
# Two resource classes (they mirror nexus-kit's Root):
#   BUNDLED  — packed INTO the executable, read via Root.internal(...)
#   EXTERNAL — shipped NEXT TO the executable by nexus-kit build:
#              .env(.example), resources/ — read via Root.external(...)
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 — SPECPATH is provided by PyInstaller


def bundled(src: str, dest: str | None = None) -> tuple[str, str]:
    return (str(ROOT / src), dest or src)


BUNDLED = [
    # bundled("app/templates"),
    # bundled("app/static"),
]

a = Analysis(  # noqa: F821
    [str(ROOT / "main.py")],
    pathex=[],
    binaries=[],
    datas=BUNDLED,
    hiddenimports=[
        # dynamic imports PyInstaller cannot see, e.g.:
        # *collect_submodules("engineio"),   (from PyInstaller.utils.hooks import collect_submodules)
    ],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="{{APP_NAME}}",
    console=True,  # False for windowed apps — stdout logging goes nowhere then, by design
    upx=False,
    runtime_tmpdir=None,  # onefile: unpacks to _MEIPASS — the Root.internal(...) base
)
''',
}

# When PyInstaller is not installed in the app's venv, `nexus-kit build` falls
# back to `uv run --with` using this pin — an unpinned tool would make last
# month's build script produce a different binary. For reproducible builds add
# pyinstaller to the app's dev group instead (uv.lock then pins it exactly).
_PYINSTALLER_FALLBACK = "pyinstaller>=6,<7"


def _new(app_name: str) -> None:
    root = Path(app_name)

    if root.exists():
        print(f"Error: '{app_name}' already exists")
        sys.exit(1)

    root.mkdir()

    nexus_ref = version("nexus-kit")
    for rel_path, content in _TEMPLATES.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = content.replace("{{APP_NAME}}", app_name).replace("{{NEXUS_REF}}", nexus_ref)
        path.write_text(content, encoding="utf-8")

    print(f"Created {app_name}/")
    print("")
    print(f"  cd {app_name}")
    print("")
    print("  # install dependencies:")
    print("  uv sync                  # uv")
    print("  pip install -e .         # pip")
    print("")
    print("  python main.py")


def _ensure_gitignore() -> None:
    gitignore = Path(".gitignore")
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    changed = False
    if "*.spec" in lines:
        # a leftover from older scaffolds — it would ignore the freshly generated app.spec
        lines.remove("*.spec")
        print("  .gitignore: removed '*.spec' — app.spec is source now")
        changed = True
    for needed in ("build/", "dist/"):
        if needed not in lines:
            lines.append(needed)
            print(f"  .gitignore: added '{needed}'")
            changed = True
    if changed:
        gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _freeze(exe_name: str | None) -> None:
    if not Path("main.py").exists():
        print("Error: main.py not found — run `nexus-kit freeze` from the application root")
        sys.exit(1)

    name = exe_name or Path.cwd().name
    for rel_path, content in _FREEZE_TEMPLATES.items():
        path = Path(rel_path)
        if path.exists():
            print(f"  skip {rel_path} (already exists)")
            continue
        path.write_text(content.replace("{{APP_NAME}}", name), encoding="utf-8", newline="\n")
        print(f"  created {rel_path}")

    _ensure_gitignore()

    print("")
    print("  # build (any platform):")
    print("  nexus-kit build")
    print("")
    print(f"  # result: dist/{name} (.exe on Windows) — BUNDLED data inside (Root.internal),")
    print("  # resources/ copied next to it (Root.external).")
    print("  # Frozen targets need Windows 10+ / any modern linux or macos (Python 3.12 floor).")


def _run_pyinstaller() -> int:
    import importlib.util
    import shutil
    import subprocess

    if importlib.util.find_spec("PyInstaller") is not None:
        # The app venv owns the PyInstaller version (add it to your dev group;
        # uv.lock then pins it exactly — reproducible builds).
        command = [sys.executable, "-m", "PyInstaller", "app.spec"]
    elif shutil.which("uv") is not None:
        print(f"  PyInstaller not installed — falling back to: uv run --with '{_PYINSTALLER_FALLBACK}'")
        print("  (for reproducible builds: uv add --dev pyinstaller)")
        command = ["uv", "run", "--with", _PYINSTALLER_FALLBACK, "pyinstaller", "app.spec"]
    else:
        print("Error: PyInstaller is not installed and uv is not on PATH.")
        print("  Fix: uv add --dev pyinstaller   (or: pip install pyinstaller)")
        return 1
    return subprocess.run(command).returncode


def _build(copy_env: bool) -> None:
    import shutil

    if not Path("app.spec").exists():
        print("Error: app.spec not found — run `nexus-kit freeze` first")
        sys.exit(1)

    for stale in ("build", "dist"):
        if Path(stale).exists():
            shutil.rmtree(stale)

    code = _run_pyinstaller()
    if code != 0 or not Path("dist").exists():
        print("Error: PyInstaller build failed")
        sys.exit(code or 1)

    # EXTERNAL resources — read via Root.external(...), must sit next to the executable.
    if Path("resources").is_dir():
        shutil.copytree("resources", Path("dist") / "resources")
        print("  copied resources/ next to the binary")
    dist = Path("dist")
    if copy_env and Path(".env").exists():
        shutil.copy2(".env", dist / ".env")
        print("  copied .env next to the binary (--env: it may contain secrets — ship deliberately)")
    elif Path(".env.example").exists():
        if copy_env:
            # --env asked to ship real config; with no .env the honest fallback
            # is the template, so dist/ is never left without one silently.
            print("  WARNING: --env requested but .env not found — shipping .env.example instead")
        shutil.copy2(".env.example", dist / ".env.example")
        print("  copied .env.example (the binary reads .env next to itself — fill it on the target machine;")
        print("  use `nexus-kit build --env` to ship your real .env deliberately)")
    else:
        looked_for = ".env or .env.example" if copy_env else ".env.example"
        print(f"  no {looked_for} found — dist/ ships without a config template; create .env on the target machine")

    built = sorted(p.name for p in Path("dist").iterdir())
    print("")
    print(f"  Done: dist/ -> {', '.join(built)}")


# --- sync-ai: mirror the AI guides of installed nexus-kit packages into .ai/ ---
#
# pip/uv have no post-install hooks, so a freshly installed satellite cannot
# announce itself to the app's AI docs. `nexus-kit sync-ai` is the explicit
# ritual instead: every satellite ships `<package>/.ai/guide.md` inside its
# wheel, and this command mirrors those into the app's `.ai/` — plus refreshes
# the kernel cheat sheet to the installed kernel version. Managed files are
# recognized by the stamp; anything unstamped is user-owned and untouchable.
#
# What this is careful about:
#   1. It scans the APPLICATION's environment (the .venv beside main.py), not
#      the interpreter running the CLI — so `nexus-kit` installed as a global
#      uv tool still sees the satellites in the project venv, and the kernel
#      version pin is the app's, not the CLI's.
#   2. A guide is INSTRUCTIONS an AI assistant will follow. The `nexus-kit-*`
#      name filter only stops accidental/transitive guides; it is NOT a trust
#      boundary (anyone can publish `nexus-kit-evil`). So a satellite's guide is
#      mirrored only once its package is on the app's trust list — the kernel is
#      trusted implicitly, everything else is opt-in via `--trust`.
#   3. It never deletes without an explicit `--prune`; a plain run only
#      creates/updates.

_SYNC_STAMP = re.compile(r"^<!-- nexus-kit sync-ai: (?P<dist>\S+) (?P<version>\S+) ")

# The pre-0.4.10 scaffold wrote this file with no stamp; it is unmistakably ours,
# so sync-ai adopts and refreshes it instead of treating it as user-owned.
_LEGACY_KERNEL_SHEET_HEADER = "# nexus-kit — quick reference"

_TRUST_FILE = Path(".ai") / "trusted-guides.txt"
_TRUST_HEADER = (
    "# Packages whose AI guides `nexus-kit sync-ai` may mirror into .ai/.\n"
    "# A guide is instructions your AI assistant will follow — trust deliberately.\n"
    "# One distribution name per line; add with `nexus-kit sync-ai --trust <name>`.\n"
)


def _normalize(dist_name: str) -> str:
    return re.sub(r"[-_.]+", "-", dist_name).lower()


def _stamp(dist: str, dist_version: str) -> str:
    return (
        f"<!-- nexus-kit sync-ai: {dist} {dist_version} — generated; "
        "refresh with `nexus-kit sync-ai`, do not edit by hand -->\n"
    )


def _is_nexus_kit_namespace(dist_name: str) -> bool:
    normalized = _normalize(dist_name)
    return normalized == "nexus-kit" or normalized.startswith("nexus-kit-")


def _app_site_packages() -> Path | None:
    """The application venv's site-packages (the env that will RUN the app),
    or None if there is no `.venv` beside main.py to introspect."""
    venv = Path(".venv")
    if not venv.is_dir():
        return None
    candidates = [venv / "Lib" / "site-packages"]  # Windows layout
    candidates += sorted(venv.glob("lib/python*/site-packages"))  # POSIX layout
    for site in candidates:
        if site.is_dir():
            return site
    return None


def _distributions(search_path: list[str] | None):
    from importlib.metadata import distributions

    return distributions(path=search_path) if search_path else distributions()


def _app_dist_version(search_path: list[str] | None, dist_name: str) -> str | None:
    """The version of `dist_name` as installed in the scanned environment
    (the app venv), independent of the interpreter running the CLI."""
    target = _normalize(dist_name)
    for dist in _distributions(search_path):
        if _normalize(dist.metadata["Name"]) == target:
            return dist.version
    return None


def _installed_ai_guides(search_path: list[str] | None) -> dict[str, tuple[str, str]]:
    """dist name -> (version, guide text) for every installed `nexus-kit-*`
    distribution shipping an embedded AI guide (`<package>/.ai/guide.md`).

    `search_path` selects the environment to scan (the app venv's
    site-packages); None falls back to the running interpreter's sys.path."""
    guides: dict[str, tuple[str, str]] = {}
    for dist in _distributions(search_path):
        name = dist.metadata["Name"]
        if not _is_nexus_kit_namespace(name):
            continue  # not ours — never a write channel into AI-read files
        for file in dist.files or []:
            if file.parts[-2:] == (".ai", "guide.md"):
                located = Path(str(file.locate()))
                if located.is_file():
                    guides[name] = (dist.version, located.read_text(encoding="utf-8"))
                break
    return guides


def _load_trusted() -> set[str]:
    if not _TRUST_FILE.exists():
        return set()
    return {
        _normalize(line)
        for raw in _TRUST_FILE.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    }


def _add_trusted(names: list[str]) -> None:
    _TRUST_FILE.parent.mkdir(exist_ok=True)
    have = _load_trusted()
    fresh = [n for n in names if _normalize(n) not in have]
    if not fresh:
        return
    body = _TRUST_FILE.read_text(encoding="utf-8") if _TRUST_FILE.exists() else _TRUST_HEADER
    if not body.endswith("\n"):
        body += "\n"
    body += "".join(f"{n}\n" for n in fresh)
    _TRUST_FILE.write_text(body, encoding="utf-8")
    for n in fresh:
        print(f"  trusted {n}")


def _stamp_kind(path: Path, name: str) -> str:
    """'stamped' if the file carries our stamp, 'legacy' if it is the known
    pre-0.4.10 generated kernel cheat sheet, '' if user-owned (do not touch)."""
    head = path.read_text(encoding="utf-8").split("\n", 1)[0]
    if _SYNC_STAMP.match(head):
        return "stamped"
    if name == "nexus-kit" and head.startswith(_LEGACY_KERNEL_SHEET_HEADER):
        return "legacy"
    return ""


def _write_guide(ai_dir: Path, name: str, dist_version: str, content: str) -> None:
    path = ai_dir / f"{name}.md"
    if path.exists():
        kind = _stamp_kind(path, name)
        if not kind:
            print(f"  skip {path} (no sync-ai stamp — user-owned)")
            return
        if path.read_text(encoding="utf-8") == content:
            return
        if kind == "legacy":
            # An unstamped legacy file may carry the user's own edits; never
            # discard them silently — keep a one-time .orig before migrating.
            backup = path.with_name(path.name + ".orig")
            if not backup.exists():
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"  kept your previous {path.name} as {backup.name} before migrating")
        path.write_text(content, encoding="utf-8")
        print(f"  updated {path} ({name} {dist_version})")
    else:
        path.write_text(content, encoding="utf-8")
        print(f"  created {path} ({name} {dist_version})")


def _sync_ai(prune: bool, trust: list[str]) -> None:
    if not Path("main.py").exists():
        print("Error: main.py not found — run `nexus-kit sync-ai` from the application root")
        sys.exit(1)

    site = _app_site_packages()
    if site is not None:
        print(f"  scanning the application environment: {site}")
        search_path: list[str] | None = [str(site)]
    else:
        print("  no .venv found next to main.py — scanning the current interpreter")
        print("  (run `uv run nexus-kit sync-ai` so the project environment is scanned)")
        search_path = None

    ai_dir = Path(".ai")
    ai_dir.mkdir(exist_ok=True)
    if trust:
        _add_trusted(trust)
    trusted = _load_trusted()

    discovered = _installed_ai_guides(search_path)
    guides: dict[str, tuple[str, str]] = {}
    untrusted: list[tuple[str, str]] = []
    for name, (dist_version, text) in discovered.items():
        if _normalize(name) == "nexus-kit":
            continue  # the kernel is handled below from the template, always
        if _normalize(name) in trusted:
            guides[name] = (dist_version, _stamp(name, dist_version) + text)
        else:
            untrusted.append((name, dist_version))

    # The kernel's contribution is the app-facing cheat sheet (from the template),
    # pinned to the version installed in the APP env — not the CLI's own version,
    # which is why a global `nexus-kit` no longer writes a wrong ~= pin.
    cli_version = version("nexus-kit")
    app_version = _app_dist_version(search_path, "nexus-kit") or cli_version
    kernel_body = _TEMPLATES[".ai/nexus-kit.md"].replace("{{NEXUS_REF}}", app_version)
    if app_version != cli_version:
        # The pin is the app's, but the body can only be THIS CLI's template —
        # it may describe features the app's kernel lacks. Say so IN the file, so
        # an agent reading it later (not just whoever watched stdout) is warned.
        print(f"  kernel pin uses the app's nexus-kit {app_version} (this CLI is {cli_version});")
        print("  the cheat-sheet body is this CLI's — run via `uv run` for a body that matches too")
        warning = (
            f"<!-- WARNING: this body was generated by nexus-kit {cli_version}, but the app runs "
            f"nexus-kit {app_version}; features described here may not exist in your kernel. "
            "Run `uv run nexus-kit sync-ai` for a version-matched body. -->\n"
        )
        head, _, rest = kernel_body.partition("\n")  # keep the stamp first, warning second
        kernel_body = f"{head}\n{warning}{rest}"
    guides["nexus-kit"] = (app_version, kernel_body)

    for name, (dist_version, content) in sorted(guides.items()):
        _write_guide(ai_dir, name, dist_version, content)

    # A guide we are no longer mirroring must not stay in .ai/*.md where the
    # assistant keeps reading it — this includes a satellite that is installed
    # but no longer trusted (e.g. auto-mirrored by 0.4.10/0.4.11 before the trust
    # gate existed). Move such stamped files out of the read path by default
    # (quarantine, never silently delete); --prune deletes them for real.
    handled = {_normalize(name) for name in guides}
    for path in sorted(ai_dir.glob("*.md")):
        if _normalize(path.stem) in handled:
            continue
        if _stamp_kind(path, path.stem) != "stamped":
            continue  # user-owned / unrelated .md — never touch
        installed = any(_normalize(n) == _normalize(path.stem) for n in discovered)
        reason = "installed but not trusted" if installed else "package not installed"
        _retire(path, prune, reason)

    if untrusted:
        print("")
        print("  These installed packages ship an AI guide but are not trusted yet")
        print("  (a guide is instructions your assistant will follow — review it first):")
        for name, dist_version in sorted(untrusted):
            print(f"    {name} {dist_version}")
        joined = " ".join(sorted(name for name, _ in untrusted))
        print(f"  trust with: nexus-kit sync-ai --trust {joined}")

    print("")
    print("  .ai/ is in sync with the trusted nexus-kit packages.")


def _retire(path: Path, prune: bool, reason: str) -> None:
    """Get a no-longer-mirrored guide out of the assistant's read path.
    Default: quarantine to `<name>.md.untrusted` (kept, but not a `*.md` guide).
    With --prune: delete outright."""
    if prune:
        path.unlink()
        print(f"  pruned {path} ({reason})")
    else:
        quarantine = path.with_name(path.name + ".untrusted")
        path.replace(quarantine)  # atomic move; out of the *.md glob the agent reads
        print(f"  quarantined {path} -> {quarantine.name} ({reason}; --prune to delete)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="nexus-kit", description="nexus-kit application kernel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new application")
    p_new.add_argument("app_name")

    p_freeze = sub.add_parser("freeze", help="generate the PyInstaller spec (app.spec)")
    p_freeze.add_argument("name", nargs="?", help="executable name (defaults to the directory name)")

    p_build = sub.add_parser("build", help="clean-build dist/ from app.spec")
    p_build.add_argument("--env", action="store_true", help="ship your real .env into dist/ (may contain secrets)")

    p_sync = sub.add_parser("sync-ai", help="mirror trusted nexus-kit packages' AI guides into .ai/")
    p_sync.add_argument("--trust", nargs="+", metavar="PKG", default=[],
                        help="trust these packages' guides (records consent in .ai/trusted-guides.txt)")
    p_sync.add_argument("--prune", action="store_true",
                        help="delete guides of uninstalled/untrusted packages instead of quarantining them")

    args = parser.parse_args()
    if args.command == "new":
        _new(args.app_name)
    elif args.command == "freeze":
        _freeze(args.name)
    elif args.command == "build":
        _build(copy_env=args.env)
    elif args.command == "sync-ai":
        _sync_ai(prune=args.prune, trust=args.trust)

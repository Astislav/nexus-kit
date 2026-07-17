import sys
from importlib.metadata import version
from pathlib import Path


_TEMPLATES: dict[str, str] = {
    "main.py": """\
import faulthandler

from app.application import Application
from app.config.di import DI_CONFIG
from app.config.environment import Environment
from nexus_kit import Root
from nexus_kit.impl import ContainerInjector

if __name__ == "__main__":
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

This app is built on the **nexus-kit** framework. Its API, the bootstrap pattern and the
gotchas are in `.ai/nexus-kit.md` — read it before touching DI, config or the composition
root (`app/config/di.py`). Keep this file thin: put engineering discipline in `.ai/`
and only repo-specific facts here.
""",
    ".ai/nexus-kit.md": """\
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
| `Root` | `nexus_kit` | paths: `Root.internal(*p)` (bundled assets) / `Root.external(*p)` (files next to the exe — or next to `main.py` in dev: `.env`, db) |
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

`nexus-kit freeze` (run from the app root) generates `app.spec` + `build.bat` +
`build.sh` and fixes `.gitignore` (`dist/`, `build/`; `app.spec` is source).
Two resource classes mirror `Root`: BUNDLED data is listed in `app.spec` and read
via `Root.internal(...)`; EXTERNAL files (`.env`, `resources/`) are copied next to
the exe by the build script and read via `Root.external(...)`. Frozen targets need
Windows 10+ or any modern linux/macos (the Python 3.12 floor).

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
#   BUNDLED  — packed INTO the exe, read via Root.internal(...)
#   EXTERNAL — shipped NEXT TO the exe by the build script (see build.bat /
#              build.sh), read via Root.external(...): .env, resources/, db
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
    "build.bat": '''\
@echo off
rem Build {{APP_NAME}}.exe — generated by `nexus-kit freeze`
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

uv run --with pyinstaller pyinstaller app.spec || exit /b 1

rem EXTERNAL resources — read via Root.external(...), must sit next to the exe
if exist .env copy .env dist\\ >nul
if exist resources xcopy /e /i /q resources dist\\resources >nul

echo.
echo Done: dist\\{{APP_NAME}}.exe
''',
    "build.sh": '''\
#!/usr/bin/env sh
# Build {{APP_NAME}} — generated by `nexus-kit freeze`
set -e
rm -rf build dist

uv run --with pyinstaller pyinstaller app.spec

# EXTERNAL resources — read via Root.external(...), must sit next to the binary
[ -f .env ] && cp .env dist/
[ -d resources ] && cp -r resources dist/resources

echo
echo "Done: dist/{{APP_NAME}}"
''',
}


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
        newline = "\r\n" if rel_path.endswith(".bat") else "\n"  # .sh must be LF even when built on Windows
        path.write_text(content.replace("{{APP_NAME}}", name), encoding="utf-8", newline=newline)
        print(f"  created {rel_path}")

    _ensure_gitignore()

    print("")
    print("  # build:")
    print("  build.bat                # windows")
    print("  sh build.sh              # linux / macos")
    print("")
    print(f"  # result: dist/{name}[.exe] — BUNDLED data inside (Root.internal),")
    print("  # .env and resources/ copied next to it (Root.external).")
    print("  # Frozen targets need Windows 10+ / any modern linux or macos (Python 3.12 floor).")


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "new":
        _new(args[1])
    elif len(args) >= 1 and args[0] == "freeze":
        _freeze(args[1] if len(args) > 1 else None)
    else:
        print("Usage:")
        print("  nexus-kit new <app-name>     scaffold a new application")
        print("  nexus-kit freeze [exe-name]  add PyInstaller packaging (app.spec + build scripts)")
        sys.exit(1)

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
*.spec
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

## What nexus does NOT provide (you hand-roll these)

Signal handling (`ServiceRunner` never grabs SIGINT/SIGTERM — exit is triggered by
uvicorn, Qt `aboutToQuit`, or your own code); a background-service/worker base;
a repository/DB layer; a test harness; HTTP/routing/retries.
""",
}


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "new":
        print("Usage: nexus-kit new <app-name>")
        sys.exit(1)

    app_name = sys.argv[2]
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

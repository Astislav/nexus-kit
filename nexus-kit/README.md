# nexus-kit

[![PyPI](https://img.shields.io/pypi/v/nexus-kit)](https://pypi.org/project/nexus-kit/)
[![Python](https://img.shields.io/pypi/pyversions/nexus-kit)](https://pypi.org/project/nexus-kit/)
[![CI](https://github.com/Astislav/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/Astislav/nexus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Astislav/nexus/blob/master/LICENSE)

A minimal application kernel for long-lived Python apps: one entry point,
typed config, constructor DI, logger channels, service lifecycle — and paths
that survive PyInstaller.

Install [`nexus-kit`](https://pypi.org/project/nexus-kit/), import `nexus_kit`.

[Source on GitHub](https://github.com/Astislav/nexus) ·
[Issues](https://github.com/Astislav/nexus/issues) ·
[Releases](https://github.com/Astislav/nexus/releases)

## Why

If you build long-lived Python apps **outside a web framework's cradle** — a
Qt tool driving hardware, a pygame game, a Windows daemon, an API server
where uvicorn is just one service among many — you end up hand-rolling the
same bootstrap in every repo: an entry point, `.env` parsing, wiring services
together, logging setup, ordered start/stop, and the `sys._MEIPASS` dance for
frozen builds.

nexus-kit is that bootstrap extracted once and turned into a convention. Every
app gets the same shape: `main.py` is four lines, config is a typed class,
services declare their dependencies in constructors, long-lived services
start in order and stop in reverse — guaranteed. Your fifth app looks like
your first, and anyone (human or AI assistant) who has seen one has seen
them all.

## Who it's for

- You ship Python as **PyInstaller executables** and are tired of path bugs
  that only appear after freezing.
- You maintain **several apps** — web and not — and want them all shaped the
  same instead of each inventing its own bootstrap.
- You want **constructor injection without magic**: one explicit
  `{Interface: Implementation}` dict, no string keys, no globals, no
  auto-scanning.
- Your app has **services that must start in order and stop cleanly** —
  DB pools, pollers, device monitors, an embedded HTTP server.

## Who it's NOT for

- **Short scripts.** A module with functions is already dependency
  injection. This would be ceremony.
- **Apps living happily inside FastAPI/Django conventions.** Their lifespan
  and DI are enough; nexus-kit solves the world outside that cradle.
- **Teams that want a mainstream stack.** This is an opinionated personal
  kernel: conventions over ecosystem, no Stack Overflow answers.

## What it is, honestly

Opinionated glue — not invention. Config is stock
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
DI is stock [injector](https://injector.readthedocs.io/); nexus-kit adds the
parts nobody packages: the `Root` path resolver for frozen builds, typed
logger channels, the `ServiceRunner` lifecycle, a scaffolder, and the
convention that ties them together. Extracted from real production apps
(a Qt hardware-control desk, a messaging gateway, forensic analytics
services), not designed in a vacuum.

## “Is this even pythonic?” — an honest answer

**“This looks like Java.”** Partially guilty. `GreeterInterface` is
nominal typing; current Python fashion is structural (`Protocol`). We
chose ABCs deliberately: the contract is visible at the declaration, and
violations fail when the container builds the graph — not at 3 a.m. when
the frozen executable on someone else's machine first hits the missing method.

Now check what the actual Zen says: *explicit is better than implicit*.
One `DI_CONFIG` dict you can read. A `SERVICES` list that *is* the
startup order. No decorator scanning, no string keys, no import-time side
effects, no metaclasses. nexus-kit breaks Python **fashion**, not Python
**philosophy** — plenty of "pythonic" frameworks resolve your
dependencies by magic and call it elegance.

## Install

```bash
# uv
uv add nexus-kit

# pip
pip install nexus-kit
```

Requires Python 3.12+. Ships with [injector](https://injector.readthedocs.io/) and
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) —
no extras, everything works out of the box.

## Bootstrap a new app

```bash
nexus-kit new my-app
cd my-app

# install dependencies:
uv sync          # uv
pip install -e . # pip

python main.py
# [ticker] started (every 0.7s)
# [my-app] running for 3.0s — Ctrl+C to stop early
# tick #1
# tick #2
# tick #3
# tick #4
# [ticker] stopped after 4 ticks
```

And when it's time to ship it as a single executable:

```bash
nexus-kit freeze          # once: generate app.spec
nexus-kit build           # every release: clean build → dist/my-app  (.exe on Windows)
```

See [Freezing your app](#freezing-your-app-pyinstaller) for what goes
inside the executable vs next to it.

## What you get

```
my-app/
├── main.py                          # entry point — the whole bootstrap, 4 lines
├── pyproject.toml
├── .env
└── app/
    ├── application.py               # SERVICES + ServiceRunner around the main loop
    ├── config/
    │   ├── di.py                    # DI_CONFIG = {Interface: Implementation}
    │   └── environment.py           # typed fields read from .env
    └── services/
        ├── ticker.py                # worker thread with clean start/stop (ServiceInterface)
        ├── reporter_interface.py    # a swappable seam
        └── console_reporter.py     # its default implementation
```

## How it fits together

```python
# main.py — the whole bootstrap
env       = Environment(Root.external(".env"))  # 1. load typed config
container = ContainerInjector(DI_CONFIG)         # 2. wire up services
container.set(Environment, env)                  # 3. make config injectable
Application(env, container).run()                # 4. start the app
```

| File | Role |
|------|------|
| `app/config/environment.py` | Declare config fields — read from `.env` automatically |
| `app/config/di.py` | Register services — `{Interface: Implementation}` |
| `app/application.py` | Entry point — resolve services, own the `run()` lifecycle |

## Environment

`EnvironmentInterface` is a [Pydantic BaseSettings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) subclass.
Add typed fields — they are read from `.env` automatically:

```python
# app/config/environment.py
from nexus_kit.interfaces import EnvironmentInterface

class Environment(EnvironmentInterface):
    APP_NAME: str = "my-app"
    DEBUG: bool = False
    DB_URL: str = "sqlite:///data.db"
```

`.env` is passed at startup via `Root.external(".env")` (see below):

```python
env = Environment(Root.external(".env"))
```

Fields can be overridden at runtime with environment variables — Pydantic picks them up automatically.

`Environment` is also bound into the container at startup, so services can inject it directly:

```python
# main.py (generated by `nexus-kit new`)
env = Environment(Root.external(".env"))
container = ContainerInjector(DI_CONFIG)
container.set(Environment, env)   # ← makes env injectable
Application(env, container).run()
```

This means any service can receive config via `@inject` without going through `Application`:

```python
from injector import inject, singleton
from app.config.environment import Environment

@singleton
class DatabaseService:
    @inject
    def __init__(self, env: Environment) -> None:
        self._url = env.DB_URL
```

## Paths

`Root` resolves paths correctly in both development and PyInstaller-bundled executables.

```python
from nexus_kit import Root

# next to the executable (or next to main.py in dev) — user data, configs, output
config = Root.external(".env")
db     = Root.external("data", "app.db")

# inside the bundle (or next to main.py in dev) — shipped assets, templates
html   = Root.internal("templates", "report.html")
```

| Method | Dev (plain Python) | Bundled (PyInstaller) |
|--------|--------------------|-----------------------|
| `Root.external(...)` | `dir(main.py) / path` | `dir(executable) / path` |
| `Root.internal(...)` | `dir(main.py) / path` | `_MEIPASS / path` |

In dev the anchor is the entry script's directory (not the current working
directory), so launching `python d:/apps/game/main.py` from anywhere — an IDE,
a task scheduler, a shortcut — resolves the same paths as running it in place.

Use `external` for anything the user owns (configs, databases, output files).
Use `internal` for assets you ship inside the bundle (templates, images, default configs).

## Freezing your app (PyInstaller)

`Root` is one half of the packaging story; the CLI is the other:

```bash
cd my-app
nexus-kit freeze          # once: generate app.spec (executable name = directory name)
nexus-kit build           # every release: clean build → dist/my-app  (.exe on Windows)
```

- **`freeze`** generates **`app.spec`** — with a `BUNDLED` list for data you
  ship *inside* the executable (read via `Root.internal(...)`) — and fixes
  `.gitignore`. The spec is source: commit it, grow its `BUNDLED` and
  `hiddenimports` lists as your app grows.
- **`build`** cleans `build/`+`dist/`, runs PyInstaller, then copies the
  EXTERNAL files *next to* the binary — where `Root.external(...)` looks in
  a frozen build: `resources/` (if present) and `.env.example` as an
  operator template. Your real **`.env` never ships by default** — use
  `nexus-kit build --env` to ship it deliberately (appliance-style deploys).

One command, every platform — no `.bat`/`.sh` to keep in sync.
Reproducibility: add PyInstaller to your dev group (`uv add --dev
pyinstaller`) so `uv.lock` pins its exact version; without it, `build`
falls back to `uv run --with "pyinstaller>=6,<7"`. Frozen targets need
Windows 10+ or any modern Linux/macOS (the Python 3.12 floor). The whole
path — scaffold → freeze → build → run the executable with `.env` beside
it — is exercised by this repo's CI on Windows, Linux and macOS on every
push.

### Deployment is a file

`--env` is not an escape hatch — for a whole class of software it is the
point. The automation you (or your AI assistant) built in an afternoon
and want to hand to the team *today*, without knowing whether it will
stick: the right amount of deploy infrastructure for that bet is zero.
`nexus-kit build --env` → one file, config riding along → send it in the
chat. No Docker, no registry, no pipeline; the machine running it doesn't
even need Python. If the tool takes root, graduate deliberately (drop
`--env`, ship `.env.example`, pin PyInstaller, add CI). If it dies, you
delete one file — not a deployment.

## Logging

`NamedLogger` is a base for typed, DI-injectable logger channels — subclass
it, set `name`, and inject the subclass by type. No string-keyed
`logging.getLogger(...)` calls scattered through the codebase:

```python
# app/loggers.py
from injector import singleton
from nexus_kit.logging import NamedLogger

@singleton
class SessionLogger(NamedLogger):
    name = "app.session"

@singleton
class SenderLogger(NamedLogger):
    name = "app.sender"
```

```python
# app/core/session_manager.py
from injector import inject, singleton
from app.loggers import SessionLogger

@singleton
class SessionManager:
    @inject
    def __init__(self, log: SessionLogger) -> None:
        self._log = log

    def start(self) -> None:
        self._log.info("Session manager started")
```

Each subclass gets its own `StdoutHandler` (console, one shared instance)
wired up automatically — no duplicate-handler bugs, no manual `addHandler`.

**Custom format** — *where* logs go (`StdoutHandler`) and *how they look*
(`LogFormatter`) are separate, like in stdlib `logging`. Subclass
`LogFormatter` and rebind it — no need to touch the handler:

```python
# app/loggers.py
from nexus_kit.logging import LogFormatter

class JsonFormatter(LogFormatter):
    format_string = '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
```

```python
# app/config/di.py
DI_CONFIG = {
    LogFormatter: JsonFormatter,
    ...
}
```

**Extra handlers** (e.g. forwarding logs to a UI widget) — override `__init__`
and add the handler after calling `super().__init__(handler)`:

```python
@singleton
class SessionLogger(NamedLogger):
    name = "app.session"

    @inject
    def __init__(self, handler: StdoutHandler, ui_handler: LogViewHandler) -> None:
        super().__init__(handler)
        self.addHandler(ui_handler)
```

## Services & lifecycle

`ServiceInterface` + `ServiceRunner` manage long-lived services: started in
declaration order, stopped in reverse — guaranteed, even when startup or the
app body crashes.

```python
# a service — sync or async, the runner handles both
from injector import singleton
from nexus_kit.interfaces import ServiceInterface

@singleton
class Database(ServiceInterface):
    async def start(self) -> None: ...   # open the pool
    async def stop(self) -> None: ...    # close the pool (must be idempotent)
```

```python
# app/application.py — async app (uvicorn, workers)
from nexus_kit.impl import ServiceRunner

class Application(ApplicationInterface):
    SERVICES = [Database, WebhookDispatcher, HttpApiService]  # startup order

    def run(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        async with ServiceRunner(self._container, self.SERVICES):
            await self._container.get(HttpApiService).wait()
        # leaving the block stops everything in reverse order
```

Sync apps (pygame, Qt with worker threads) use the plain context manager:

```python
    def run(self) -> None:
        with ServiceRunner(self._container, self.SERVICES):
            self._main_loop()
```

Guarantees:

- start in order, stop in reverse — on normal exit, exception, Ctrl+C;
- crash-safe startup: if the N-th `start()` fails, that service's own
  `stop()` is still called (write `stop()` to tolerate a partially
  initialized state), then the already started N-1 are stopped in reverse
  and the error re-raises;
- one failing `stop()` doesn't block the rest — it is logged and teardown
  continues;
- in the async context each **async** `stop()` is bounded by `stop_grace`
  seconds (default 10), then cancelled; a **sync** `stop()` runs inline and
  is not bounded — offloading it to a thread would break thread-affine
  teardown (Qt, COM).

The runner installs **no signal handlers** — who triggers the exit is your
app's business (uvicorn's own handlers, Qt's `aboutToQuit`, or your own).

## Add a service

**1. Define an interface (a swappable seam):**

```python
# app/services/reporter_interface.py
from abc import ABC, abstractmethod

class ReporterInterface(ABC):
    @abstractmethod
    def report(self, tick: int) -> None: ...
```

**2. Implement it:**

```python
# app/services/console_reporter.py
from injector import singleton
from app.services.reporter_interface import ReporterInterface

@singleton
class ConsoleReporter(ReporterInterface):
    def report(self, tick: int) -> None:
        print(f"tick #{tick}")
```

**3. Register in DI:**

```python
# app/config/di.py
from app.services.console_reporter import ConsoleReporter
from app.services.reporter_interface import ReporterInterface

DI_CONFIG = {
    ReporterInterface: ConsoleReporter,
}
```

**4. Inject it — by type, into a constructor, no string keys:**

```python
# app/services/ticker.py
from injector import inject, singleton
from nexus_kit.interfaces import ServiceInterface

@singleton
class Ticker(ServiceInterface):
    @inject
    def __init__(self, env: Environment, reporter: ReporterInterface) -> None:
        self._interval = env.TICK_SECONDS
        self._reporter = reporter
```

Swapping `ConsoleReporter` for a file writer, an HTTP pusher or a Qt widget
is a one-line change in `DI_CONFIG` — nothing else moves.

## What nexus-kit provides

| Symbol | Import | Description |
|--------|--------|-------------|
| `ApplicationInterface` | `nexus_kit.interfaces` | Bootstrap contract: `__init__(env, container)` + `run()` |
| `ContainerInterface` | `nexus_kit.interfaces` | DI contract: `get(cls)` + `set(cls, value)` |
| `EnvironmentInterface` | `nexus_kit.interfaces` | Typed config base (Pydantic BaseSettings) |
| `ServiceInterface` | `nexus_kit.interfaces` | Long-lived service contract: `start()` + `stop()`, sync or async |
| `Root` | `nexus_kit` | Path util for dev and PyInstaller-bundled environments |
| `ContainerInjector` | `nexus_kit.impl` | `ContainerInterface` impl via [injector](https://injector.readthedocs.io/) |
| `ServiceRunner` | `nexus_kit.impl` | Ordered start / guaranteed reverse-order stop (`with` / `async with`) |
| `NamedLogger` | `nexus_kit.logging` | Base for typed, DI-injectable logger channels |
| `StdoutHandler` | `nexus_kit.logging` | Shared console handler — *where* logs go |
| `LogFormatter` | `nexus_kit.logging` | Default log line format — *how* logs look; subclass to customize |

## What nexus-kit does NOT provide

Domain logic, UI, data access — those belong in your app.

## For AI assistants

Two machine-oriented references ship with the framework:

- [`.ai/guide.md`](https://github.com/Astislav/nexus/blob/master/nexus-kit/.ai/guide.md) —
  the full framework guide: API, conventions, lifecycle guarantees, what
  NOT to do. Point your agent at it when working in this repo or on apps
  built with nexus-kit.
- `nexus-kit new` generates the same knowledge into every scaffolded app:
  a `CLAUDE.md` pointing at `.ai/nexus-kit.md` — a self-contained cheat
  sheet pinned to the installed framework version, so an AI assistant in a
  consumer project never needs to read the framework source.

## License

MIT © Astislav Bozhevolnov

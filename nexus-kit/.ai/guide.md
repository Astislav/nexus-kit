<!-- when: bootstrapping an app, wiring DI, defining typed config, adding a service to the lifecycle, logging, or resolving PyInstaller-safe paths -->
# nexus-kit — AI Agent Guide

Context for AI assistants working in projects built with nexus-kit
(PyPI dist `nexus-kit`, import `nexus_kit`).

**Keeping these guides current:** every nexus-kit package ships its own guide;
`uv run nexus-kit guides` (re-run after `uv add`-ing, upgrading or removing any
nexus-kit package) writes them into `.nexus-kit/` and indexes them in
`.nexus-kit/map.md`, which the app's AGENTS.md mounts. The atlas is generated and
committed so it travels with the repo — never hand-edit the copies in
`.nexus-kit/`; re-run `nexus-kit guides` instead. Treat the guides as the
framework's machine contract.

## What nexus-kit is

nexus-kit is a minimal Python application framework. It provides:

- Interfaces (abstract contracts) for bootstrapping an application
- `ContainerInjector` — a concrete DI container implementation (thin wrapper over the `injector` library)
- `ServiceInterface` / `ServiceRunner` — lifecycle: ordered start, guaranteed reverse-order stop of long-lived services (sync and async)
- `Root` — a path utility that works in dev and PyInstaller-bundled environments
- A logging base (`NamedLogger` / `StdoutHandler` / `LogFormatter`), DI-injectable
- A scaffolding CLI: `nexus-kit new <app-name>`; packaging via `nexus-kit freeze`
  (generates `app.spec`: BUNDLED↔`Root.internal`) + `nexus-kit build` (clean
  cross-platform PyInstaller build; copies `resources/` and `.env.example` next
  to the binary↔`Root.external`; real `.env` ships only with `--env`)

Nexus does NOT contain domain logic, UI code, or data access. It is infrastructure only.

**Gotcha:** `@singleton`, `@inject` and `Injector` come from the third-party `injector`
package, **not** from Nexus — import them `from injector import inject, singleton`.
Nexus never re-exports them.

**Dependencies:** `injector` and `pydantic-settings` are core dependencies of nexus —
no extras, everything works out of the box.

## Package layout

```
nexus_kit/
├── interfaces/          # abstract contracts — always import from here first
│   ├── application.py   # ApplicationInterface
│   ├── container.py     # ContainerInterface
│   └── environment.py   # EnvironmentInterface
├── impl/                # concrete implementations — import explicitly
│   └── container_injector.py
├── logging/             # DI-injectable logging base
│   ├── named_logger.py  # NamedLogger
│   ├── stdout_handler.py# StdoutHandler
│   └── log_formatter.py # LogFormatter
├── cli.py               # `nexus-kit new` scaffolder
└── root.py              # Root utility
```

Import conventions:

```python
from nexus_kit.interfaces import ApplicationInterface, ContainerInterface, EnvironmentInterface
from nexus_kit.impl import ContainerInjector   # explicit — this is a concrete choice
from nexus_kit import Root
```

## Bootstrap pattern

Every nexus-based app follows this sequence in `main.py`:

```python
env = Environment(Root.external(".env"))      # 1. load config
container = ContainerInjector(DI_CONFIG)      # 2. wire dependencies
Application(env, container).run()             # 3. start app
```

`Environment` extends `EnvironmentInterface`, `Application` extends `ApplicationInterface`.
`DI_CONFIG` lives in `app/config/di.py` — it is the composition root.

## How to extend ApplicationInterface

```python
from nexus_kit.interfaces import ApplicationInterface, ContainerInterface, EnvironmentInterface

class Application(ApplicationInterface):
    def __init__(self, environment: EnvironmentInterface, container: ContainerInterface) -> None:
        self._env = environment
        self._container = container
        # resolve top-level services here:
        # self._service = container.get(SomeServiceInterface)

    def run(self) -> None:
        ...  # start event loop, server, CLI, etc.
```

## How to extend EnvironmentInterface

```python
from pathlib import Path
from injector import singleton
from nexus_kit.interfaces import EnvironmentInterface

@singleton
class Environment(EnvironmentInterface):
    DATABASE_URL: str
    DEBUG: bool = False
    MAX_WORKERS: int = 4

    def __init__(self, env_path: Path) -> None:
        super().__init__(_env_file=env_path)
```

Pydantic BaseSettings rules apply: values come from environment variables and the `.env` file.
Pass the `.env` path via `Root.external(".env")`.

## How to register services in DI

Composition root lives in `app/config/di.py`:

```python
from app.services.greeter import Greeter
from app.services.greeter_interface import GreeterInterface

DI_CONFIG = {
    GreeterInterface: Greeter,
    # Interface: ConcreteImplementation
}
```

Mark long-lived services with `@singleton`, use `@inject` for constructor injection:

```python
from injector import inject, singleton
from app.services.dep_interface import DepInterface

@singleton
class Greeter(GreeterInterface):
    @inject
    def __init__(self, dep: DepInterface) -> None:
        self._dep = dep
```

## Logging

Named logger channels are DI-injectable types, not `getLogger(str)` lookups. Subclass
`NamedLogger`, set a class-level `name`; inject the subclass by type. Change the line
format by rebinding `LogFormatter` in `DI_CONFIG` (independent of the destination handler).

```python
from injector import singleton
from nexus_kit.logging import NamedLogger, LogFormatter

@singleton
class MainLogger(NamedLogger):
    name = "app.main"

class JsonFormatter(LogFormatter):
    def format(self, record): ...   # rebind in DI_CONFIG: {LogFormatter: JsonFormatter}
```

## Lifecycle

Long-lived services implement `ServiceInterface` (`start()`/`stop()`, sync or async,
`stop()` idempotent). `Application` lists them in startup order and wraps the app body
in a `ServiceRunner` context:

```python
from nexus_kit.impl import ServiceRunner

SERVICES = [Database, WebhookDispatcher, HttpApiService]   # startup order

# async app:
async with ServiceRunner(self._container, SERVICES):
    await self._container.get(HttpApiService).wait()
# sync app (pygame, Qt):
with ServiceRunner(self._container, SERVICES):
    self._main_loop()
```

Guarantees: reverse-order stop on any exit; crash-safe startup (a failed `start()`
still gets its own best-effort `stop()`, then the already-started services roll back —
write `stop()` to tolerate partially initialized state); a failing `stop()` is logged
and teardown continues; async stops are bounded by `stop_grace` (10s default), sync
stops run inline unbounded. The runner installs no signal handlers — exit is triggered
by uvicorn, Qt `aboutToQuit`, or your own code.

## Bridging into host frameworks (the satellite pattern)

The typed lookup `ContainerInterface.get(cls: type[T]) -> T` is the core's
integration surface. A satellite bridging nexus into a host framework
(FastAPI, Qt, a CLI runner) wraps that one call into the host's OWN
dependency idiom — it does not invent a new one and does not patch the
host. Reference implementation: `nexus_kit_fastapi.Injected(cls)` — a plain
FastAPI `Depends` whose declared return type mirrors `get`'s `type[T] -> T`,
so route signatures type-check as if they held the real object. Rules:
declarative at the call site (visible in the signature, never a lookup
buried in a function body); a narrow waist (one attach point, neither side
knows the other); process-lifetime objects come from the container,
request/short-lived ones stay native to the host.

## What nexus does NOT provide (you hand-roll these)

- No signal handling — `ServiceRunner` never grabs SIGINT/SIGTERM; wire the exit
  trigger yourself (uvicorn's handlers, Qt `aboutToQuit`, own handler).
- No background-service / worker base class, no scheduling.
- No repository / persistence / DB layer.
- No testing helpers or fixtures.
- No HTTP/server/routing, retries, or middleware.
- Config is stock `pydantic-settings`; logging is a stdout stream handler only.

## Key conventions

- Abstract contracts have the `Interface` suffix: `GreeterInterface`, `UserRepositoryInterface`
- Implementations have no special suffix: `Greeter`, `UserRepository`
- One class per file; file named after the class in snake_case
- `@singleton` for long-lived managers and services
- Dynamic objects (created at runtime) use Factories: `WidgetFactoryInterface` → `WidgetFactory`
- Do not import concrete implementations outside of `di.py` (exceptions: tests, and
  the `SERVICES` list in `Application` — both are part of the composition root)

## What NOT to do

- Do not put business logic in `Application.__init__` or `main.py`
- Do not make `ContainerInterface` globally accessible — pass it only to `Application`
- Do not register primitive types (str, int, bool) in DI unless they carry policy semantics
- Do not add `@inject` to `Application.__init__` — it is constructed manually in `main.py`

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
`uv run nexus-kit sync-ai`. Keep this file thin: put engineering discipline in `.ai/`
and only repo-specific facts here.
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
each installed `nexus-kit-*` package's guide into `.ai/<dist-name>.md` and refreshes
this file. Managed files carry the header stamp above; your own `.ai/*.md` files are
never touched. A plain run only creates/updates; add `--prune` to remove guides of
packages you have uninstalled.

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
    shipped_real_env = False
    if copy_env:
        if Path(".env").exists():
            shutil.copy2(".env", Path("dist") / ".env")
            print("  copied .env next to the binary (--env: it may contain secrets — ship deliberately)")
            shipped_real_env = True
        else:
            # --env is an explicit intent to ship config; an empty dist/ would
            # be worse than the safe default, so fall back to the template.
            print("  WARNING: --env requested but .env not found — shipping .env.example instead")
    if not shipped_real_env and Path(".env.example").exists():
        shutil.copy2(".env.example", Path("dist") / ".env.example")
        print("  copied .env.example (the binary reads .env next to itself — fill it on the target machine;")
        print("  use `nexus-kit build --env` to ship your real .env deliberately)")

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
# Three things this is careful about:
#   1. It scans the APPLICATION's environment (the .venv beside main.py), not
#      the interpreter running the CLI — so `nexus-kit` installed as a global
#      uv tool still sees the satellites in the project venv, instead of seeing
#      an empty world and "removing" every guide.
#   2. It mirrors guides ONLY from the `nexus-kit-*` namespace — an arbitrary
#      (possibly transitive) dependency shipping a `.ai/guide.md` must not get
#      a write channel into files an AI assistant reads.
#   3. It never deletes without an explicit `--prune`; a plain run only
#      creates/updates.

_SYNC_STAMP = re.compile(r"^<!-- nexus-kit sync-ai: (?P<dist>\S+) (?P<version>\S+) ")

# The pre-0.4.10 scaffold wrote this file with no stamp; it is unmistakably ours,
# so sync-ai adopts and refreshes it instead of treating it as user-owned.
_LEGACY_KERNEL_SHEET_HEADER = "# nexus-kit — quick reference"


def _stamp(dist: str, dist_version: str) -> str:
    return (
        f"<!-- nexus-kit sync-ai: {dist} {dist_version} — generated; "
        "refresh with `nexus-kit sync-ai`, do not edit by hand -->\n"
    )


def _is_nexus_kit_namespace(dist_name: str) -> bool:
    normalized = re.sub(r"[-_.]+", "-", dist_name).lower()
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


def _installed_ai_guides(search_path: list[str] | None) -> dict[str, tuple[str, str]]:
    """dist name -> (version, guide text) for every installed `nexus-kit-*`
    distribution shipping an embedded AI guide (`<package>/.ai/guide.md`).

    `search_path` selects the environment to scan (the app venv's
    site-packages); None falls back to the running interpreter's sys.path."""
    from importlib.metadata import distributions

    guides: dict[str, tuple[str, str]] = {}
    for dist in distributions(path=search_path) if search_path else distributions():
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


def _managed_or_legacy(path: Path, name: str) -> bool:
    """True if sync-ai owns this file: it carries our stamp, or it is the
    known pre-0.4.10 generated kernel cheat sheet (which had no stamp)."""
    head = path.read_text(encoding="utf-8").split("\n", 1)[0]
    if _SYNC_STAMP.match(head):
        return True
    return name == "nexus-kit" and head.startswith(_LEGACY_KERNEL_SHEET_HEADER)


def _sync_ai(prune: bool) -> None:
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

    guides = {
        name: (dist_version, _stamp(name, dist_version) + text)
        for name, (dist_version, text) in _installed_ai_guides(search_path).items()
    }
    # The kernel's contribution is the app-facing cheat sheet (stamp is part of
    # the template), not its repo guide — and it always wins the "nexus-kit" slot.
    nexus_version = version("nexus-kit")
    guides["nexus-kit"] = (
        nexus_version,
        _TEMPLATES[".ai/nexus-kit.md"].replace("{{NEXUS_REF}}", nexus_version),
    )

    for name, (dist_version, content) in sorted(guides.items()):
        path = ai_dir / f"{name}.md"
        if path.exists():
            if not _managed_or_legacy(path, name):
                print(f"  skip {path} (no sync-ai stamp — user-owned)")
                continue
            if path.read_text(encoding="utf-8") == content:
                continue
            path.write_text(content, encoding="utf-8")
            print(f"  updated {path} ({name} {dist_version})")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"  created {path} ({name} {dist_version})")

    stale = []
    for path in sorted(ai_dir.glob("*.md")):
        if path.stem in guides:
            continue
        match = _SYNC_STAMP.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
        if match and match["dist"] == path.stem:
            stale.append(path)

    for path in stale:
        if prune:
            path.unlink()
            print(f"  pruned {path} (its package is no longer installed)")
        else:
            print(f"  stale {path} (package not installed — `nexus-kit sync-ai --prune` to remove)")

    print("")
    print("  .ai/ is in sync with the installed nexus-kit packages.")


def _reject_unknown_flags(flags: list[str], allowed: set[str]) -> None:
    unknown = [a for a in flags if a.startswith("-") and a not in allowed]
    if unknown:
        print(f"Error: unknown option(s): {' '.join(unknown)}")
        sys.exit(1)


def _usage() -> None:
    print("Usage:")
    print("  nexus-kit new <app-name>     scaffold a new application")
    print("  nexus-kit freeze [name]      generate the PyInstaller spec (app.spec)")
    print("  nexus-kit build [--env]      clean-build dist/ from app.spec; --env ships your real .env")
    print("  nexus-kit sync-ai [--prune]  mirror installed nexus-kit packages' AI guides into .ai/")


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "new":
        _new(args[1])
    elif len(args) >= 1 and args[0] == "freeze":
        _freeze(args[1] if len(args) > 1 else None)
    elif len(args) >= 1 and args[0] == "build":
        _reject_unknown_flags(args[1:], {"--env"})
        _build(copy_env="--env" in args[1:])
    elif len(args) >= 1 and args[0] == "sync-ai":
        _reject_unknown_flags(args[1:], {"--prune"})
        _sync_ai(prune="--prune" in args[1:])
    else:
        _usage()
        sys.exit(1)

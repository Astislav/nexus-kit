import re
import sys
from importlib.metadata import version
from pathlib import Path
from typing import NamedTuple


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
    "AGENTS.md": """\
# AGENTS.md

Instructions for AI coding agents in this repository. **This file is yours** —
edit it freely; the nexus-kit tooling never writes to it.

This app is built on the **nexus-kit** framework. The full guide for each
installed nexus-kit package lives under `.nexus-kit/`, indexed by a small map.
Read the map, then open the specific guide it points to for what you're working
on — don't load them all.

**Read `.nexus-kit/map.md`** to find the right guide for your task.
""",
    ".nexus-kit/map.md": """\
<!-- generated by nexus-kit — do not edit by hand -->
# nexus-kit — AI guide map

This atlas has not been generated yet — it holds no guides.
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
    print("  # install dependencies and generate the AI guide atlas:")
    print("  uv sync")
    print("  uv run nexus-kit update-ai-guides   # writes .nexus-kit/; AGENTS.md already mounts it")
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


# --- update-ai-guides: build the .nexus-kit atlas from the allowlisted guides ---
# (the `update-ai-guides` command; `guides` is a short alias)
#
# Every nexus-kit package (kernel and satellites) ships an `.ai/guide.md` inside
# its wheel. This command reads those — only for packages on the allowlist below —
# from the APPLICATION's environment and writes a small, always-on MAP plus one
# on-demand guide per package into `.nexus-kit/`. The user mounts ONLY the map in
# their own AGENTS.md (one stable line); this tool never edits it, and never reads
# or writes CLAUDE.md or any editor-specific file.
#
# A guide's text is injected into the agent VERBATIM through the map — the atlas is
# a delivery CHANNEL, not a content filter. The design keeps the human in control:
#   - Nothing runs this command automatically, and NO agent-read file (a guide, the
#     map, AGENTS.md) tells the agent to run it — so the set of instructions the
#     agent reads changes ONLY when the human runs `update-ai-guides` deliberately.
#   - `.nexus-kit/` is committed, so the change lands in a reviewable diff (new
#     guidance, or anything threatening). NOTE: the command writes the atlas in
#     place, so nothing forces review BEFORE the agent next reads it — the guard is
#     that the guides change only when the human runs the command, and the diff is
#     there to inspect.
#   - The allowlist (`_ALLOWED_GUIDE_PACKAGES`) limits WHICH sources are read: an
#     unrelated or malicious `nexus-kit-*` package's guide is never assembled — but
#     that is about sources, not safety, since any allowlisted guide is injected
#     as-is.
#
# Building the atlas never imports a package (the guide is read as a file), so no
# package code runs here. But installing any package already runs its code — vet
# dependencies like any code. The atlas is a convenience, not a security barrier.
# Progressive disclosure (the Skills model): the map is tiny and always in context;
# full guides are read on demand, so N satellites don't bloat it.

_ATLAS_DIR = Path(".nexus-kit")
_GUIDES_DIR = _ATLAS_DIR / "guides"
_MAP_FILE = _ATLAS_DIR / "map.md"
_DO_NOT_EDIT = "generated by nexus-kit — do not edit by hand"

# The gate. nexus-kit reads an `.ai/guide.md` ONLY from a package whose dist name
# is here — the framework author's blessing, shipped in this wheel. A package not
# on this list (an unrelated dependency, or a malicious `nexus-kit-evil`) never
# has its guide read, so nexus-kit will not carry its text into an agent's
# context. PyPI names are unique, so no one can publish under a name already here.
# Adding a satellite means adding its dist name here and releasing core — that
# release IS the vouch. (A per-app opt-in for the consumer's OWN packages was
# considered and rejected: a guide is only useful if its package follows nexus-kit
# conventions, which arbitrary packages don't — so the knob served ~nobody.)
_ALLOWED_GUIDE_PACKAGES = frozenset({
    "nexus-kit",
    "nexus-kit-fastapi",
})


class _Guide(NamedTuple):
    name: str
    version: str
    summary: str
    text: str


def _normalize(dist_name: str) -> str:
    return re.sub(r"[-_.]+", "-", dist_name).lower()


def _when_hint(guide_text: str) -> str | None:
    """A guide may declare when it is relevant with `<!-- when: ... -->` near its
    top; the map surfaces that as a routing cue so the agent opens the right guide
    without reading them all. Falls back to None (map uses the summary alone)."""
    match = re.search(r"<!--\s*when:\s*(.*?)\s*-->", guide_text, re.DOTALL)
    return " ".join(match.group(1).split()) if match else None


def _app_site_packages() -> Path | None:
    """The application venv's site-packages (the env that will RUN the app),
    or None if there is no `.venv` in the current directory to introspect."""
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


def _discover_guides(search_path: list[str] | None) -> list[_Guide]:
    """Read the `.ai/guide.md` of every ALLOWLISTED package installed in the
    scanned environment (the app venv). The allowlist (`_ALLOWED_GUIDE_PACKAGES`)
    is the gate: nexus-kit only ever carries the guide text of packages its author
    blessed, so an unrelated or malicious `nexus-kit-*` package cannot get its text
    into an agent's context through the atlas. The guide is located via the
    distribution's file list — we never import the package (no package code runs) —
    and is read only if it resolves INSIDE the distribution's own directory, so a
    RECORD entry using `..`, an absolute path, or a symlink cannot make us read a
    file elsewhere on disk."""
    guides: list[_Guide] = []
    for dist in _distributions(search_path):
        name = dist.metadata["Name"]
        if _normalize(name) not in _ALLOWED_GUIDE_PACKAGES:
            continue  # not author-blessed — its guide is never read
        try:
            root = Path(str(dist.locate_file(""))).resolve()
        except Exception:
            continue
        text = None
        for file in dist.files or []:
            if file.parts[-2:] != (".ai", "guide.md"):
                continue
            located = Path(str(file.locate())).resolve()
            if located.is_relative_to(root) and located.is_file():
                text = located.read_text(encoding="utf-8")
            break  # first .ai/guide.md entry decides — inside the tree or not at all
        if text is None:
            continue  # allowlisted but ships no guide (or its guide escaped the tree)
        summary = (dist.metadata.get("Summary") or "").strip()
        guides.append(_Guide(name, dist.version, summary, text))
    # kernel first, then alphabetical
    return sorted(guides, key=lambda g: (_normalize(g.name) != "nexus-kit", _normalize(g.name)))


def _guide_file_content(g: _Guide) -> str:
    text = g.text if g.text.endswith("\n") else g.text + "\n"
    return f"<!-- {_DO_NOT_EDIT} (from {g.name} {g.version}) -->\n{text}"


def _map_content(guides: list[_Guide]) -> str:
    lines = [
        f"<!-- {_DO_NOT_EDIT} -->",
        "# nexus-kit — AI guide map",
        "",
        "This project is built on nexus-kit. The full guide for each installed",
        "nexus-kit package is in `.nexus-kit/guides/`. Read the specific guide",
        "listed below WHEN its situation applies — don't load them all at once.",
        "",
        "## Installed guides",
        "",
    ]
    if not guides:
        lines.append("_No nexus-kit guides are installed in this environment._")
    for g in guides:
        summary = g.summary or "nexus-kit package"
        summary = summary if summary.endswith(".") else summary + "."
        read = f"Read `.nexus-kit/guides/{g.name}.md`"
        when = _when_hint(g.text)
        read = f"{read} when {when}." if when else f"{read}."
        lines.append(f"- **{g.name}** `{g.version}` — {summary} {read}")
    lines.append("")
    return "\n".join(lines)


def _atlas_files(guides: list[_Guide]) -> dict[Path, str]:
    """The full desired content of the atlas: {relative path -> content}."""
    files: dict[Path, str] = {_GUIDES_DIR / f"{g.name}.md": _guide_file_content(g) for g in guides}
    files[_MAP_FILE] = _map_content(guides)
    return files


def _mount_status() -> str | None:
    """Which of the user's agent files (if any) already mounts the map."""
    path = Path("AGENTS.md")  # AGENTS.md only — we never read CLAUDE.md or any editor-specific file
    if path.is_file() and ".nexus-kit/map.md" in path.read_text(encoding="utf-8", errors="ignore"):
        return "AGENTS.md"
    return None


def _migrate_legacy_layout() -> None:
    """Retire the 0.4.x layout the .nexus-kit atlas replaces. We only ever delete
    OUR OWN generated artifacts (stamped guides, the trust file, the quarantine,
    the *.md.untrusted quarantine copies). User content is never deleted: *.md.orig
    backups (the user's pre-migration edits that 0.4.12 saved) are kept, and an old
    unstamped `.ai/*.md` is left in place with a warning."""
    removed: list[str] = []
    unstamped: list[str] = []
    kept_orig = False
    ai = Path(".ai")
    if ai.is_dir():
        for md in sorted(ai.glob("*.md")):
            head = md.read_text(encoding="utf-8", errors="ignore").split("\n", 1)[0]
            if head.startswith("<!-- nexus-kit sync-ai:"):
                md.unlink()  # our own stamped 0.4.10+ generated copy
                removed.append(str(md))
            else:
                unstamped.append(str(md))  # 0.4.0–0.4.9 or user-authored — never delete
        for extra in sorted(ai.glob("*.md.untrusted")):
            extra.unlink()  # our own 0.4.13 quarantine copy
            removed.append(str(extra))
        kept_orig = bool(list(ai.glob("*.md.orig")))  # user's pre-migration edits — keep
        trust = ai / "trusted-guides.txt"
        if trust.exists():
            trust.unlink()
            removed.append(str(trust))
    quarantine = Path(".nexus-kit-quarantine")
    if quarantine.is_dir():
        import shutil

        shutil.rmtree(quarantine)
        removed.append(f"{quarantine}/")

    if removed:
        print("  migrated from the 0.4.x layout — removed our generated artifacts:")
        for item in removed:
            print(f"    {item}")
    if kept_orig:
        print("  kept your .ai/*.md.orig files (your pre-migration edits) — review/remove by hand")
    if unstamped:
        print("  found old unstamped guides — NOT removed (they may be your edits); review by hand:")
        for item in unstamped:
            print(f"    {item}")
    if removed or unstamped:
        print("  if your AGENTS.md/CLAUDE.md still points at .ai/, change the mount to .nexus-kit/map.md")


def _write_atlas(desired: dict[Path, str]) -> None:
    _GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    keep = {p.resolve() for p in desired}
    for existing in sorted(_GUIDES_DIR.glob("*.md")):
        if existing.resolve() not in keep:
            existing.unlink()  # package no longer installed — regenerate wholesale
            print(f"  removed {existing} (package no longer installed)")
    for path, content in sorted(desired.items(), key=lambda kv: str(kv[0])):
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        verb = "updated" if path.exists() else "created"
        path.write_text(content, encoding="utf-8")
        print(f"  {verb} {path}")


def _check_atlas(desired: dict[Path, str]) -> None:
    problems: list[str] = []
    for path, content in desired.items():
        if not path.exists():
            problems.append(f"missing {path}")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"stale {path}")
    if _GUIDES_DIR.is_dir():
        keep = {p.resolve() for p in desired}
        for existing in _GUIDES_DIR.glob("*.md"):
            if existing.resolve() not in keep:
                problems.append(f"orphan {existing}")
    if problems:
        print("  .nexus-kit is out of date — run `nexus-kit update-ai-guides`:")
        for item in sorted(problems):
            print(f"    {item}")
        sys.exit(1)
    print("  .nexus-kit is up to date.")


def _build_guides(check: bool) -> None:
    # The app root is the current directory. Anchor on any Python-project marker
    # (a pyproject.toml or a .venv) rather than a scaffold-specific main.py — real
    # apps have their own entry point, or none.
    if not Path("pyproject.toml").exists() and not Path(".venv").is_dir():
        print("Error: run `nexus-kit update-ai-guides` from your project root")
        print("  (no pyproject.toml or .venv/ found in the current directory)")
        sys.exit(1)

    site = _app_site_packages()
    if site is not None:
        print(f"  scanning the application environment: {site}")
        search_path: list[str] | None = [str(site)]
    else:
        print("  no .venv/ in the current directory — scanning the current interpreter")
        print("  (run `uv run nexus-kit update-ai-guides` so the project environment is scanned)")
        search_path = None

    guides = _discover_guides(search_path)
    desired = _atlas_files(guides)

    if check:
        _check_atlas(desired)
        return

    _migrate_legacy_layout()
    _write_atlas(desired)

    print("")
    if guides:
        print(f"  {len(guides)} guide(s) in {_ATLAS_DIR}/: " + ", ".join(g.name for g in guides))
    else:
        print(f"  no nexus-kit guides found in the app environment — {_ATLAS_DIR}/map.md is empty")
    mounted = _mount_status()
    if mounted:
        print(f"  mounted via {mounted} -> {_MAP_FILE}")
    else:
        print(f"  To let your assistant use these, add one line to your AGENTS.md pointing at {_MAP_FILE}")
        print("  (e.g. `Read .nexus-kit/map.md`). We never edit AGENTS.md — that's yours;")
        print("  `nexus-kit new` sets it up for fresh apps.")
    print("  Commit .nexus-kit/ and review the diff — that is how you see what reached your agent.")


def _print_intro() -> None:
    print("nexus-kit — an application kernel for long-lived Python apps")
    print("(one entry point, typed config, constructor DI, service lifecycle, frozen-safe paths).")
    print("")
    print("Commands:")
    print("  nexus-kit new <app>           scaffold a new app")
    print("  nexus-kit freeze              generate the PyInstaller spec (app.spec)")
    print("  nexus-kit build               build a standalone executable from the spec")
    print("  nexus-kit update-ai-guides    rebuild .nexus-kit/ — the AI-guide atlas for your agent")
    print("")
    print("About the guides: each nexus-kit package ships a machine-readable guide.")
    print("`nexus-kit update-ai-guides` collects the ones installed in your project into")
    print(".nexus-kit/ (a small map + one guide per package). YOU run it, deliberately, after")
    print("adding/upgrading/removing a nexus-kit package; nothing runs it for you. The atlas is")
    print("committed, so the change lands in a diff you can review (it writes in place, so nothing")
    print("forces review first — but the guides change only when you run this).")
    print("")
    print("Docs: https://github.com/Astislav/nexus-kit")


def main() -> None:
    import argparse

    if len(sys.argv) == 1:  # bare `nexus-kit` — a friendly intro, not an error
        _print_intro()
        return

    parser = argparse.ArgumentParser(prog="nexus-kit", description="nexus-kit application kernel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new application")
    p_new.add_argument("app_name")

    p_freeze = sub.add_parser("freeze", help="generate the PyInstaller spec (app.spec)")
    p_freeze.add_argument("name", nargs="?", help="executable name (defaults to the directory name)")

    p_build = sub.add_parser("build", help="clean-build dist/ from app.spec")
    p_build.add_argument("--env", action="store_true", help="ship your real .env into dist/ (may contain secrets)")

    p_guides = sub.add_parser(
        "update-ai-guides", aliases=["guides"],
        help="rebuild the .nexus-kit AI-guide atlas from the installed nexus-kit packages",
    )
    p_guides.add_argument("--check", action="store_true",
                          help="fail if .nexus-kit is out of date (for CI); write nothing")

    args = parser.parse_args()
    if args.command == "new":
        _new(args.app_name)
    elif args.command == "freeze":
        _freeze(args.name)
    elif args.command == "build":
        _build(copy_env=args.env)
    elif args.command in ("update-ai-guides", "guides"):
        _build_guides(check=args.check)

# Changelog

All notable changes to nexus-kit. Versioning: [semver](https://semver.org/) —
in 0.x, breaking changes bump the minor version.

## [0.5.0] — 2026-07-22

**Breaking: the AI-guide delivery is redesigned.** The 0.4.x model — copy each
package's guide into `.ai/`, gate with a trust file, quarantine orphans — was
over-built (four hardening rounds of consequences from *copying*). It is
replaced by a committed atlas discovered through entry points.

- **`nexus-kit guides` now builds `.nexus-kit/`** (the command is `guides`;
  `sync-ai` is kept as an alias): a small, always-on `map.md` — indexed with a
  *read-this-when* cue per package (from an optional `<!-- when: … -->` in each
  guide) — plus one on-demand `guides/<pkg>.md`. You mount ONLY the map in your
  own AGENTS.md/CLAUDE.md (one stable line); the guides are read on demand. This
  is progressive disclosure (the Skills model) — N satellites no longer bloat the
  agent's context. The mount is plain markdown (`Read .nexus-kit/map.md`), so it
  is not tied to any one editor; Claude Code can `@`-import it.
- **Discovery via the `nexus_kit.ai_guides` entry point**, not a name guess. A
  package opts in explicitly. The kernel is just another provider: it ships its
  own `guide.md` in the wheel, so the CLI no longer injects a version-pinned
  template — the whole global-CLI-vs-app version-mismatch class of bug is gone.
- **No trust machinery — it was security theatre.** A guide is documentation
  from a package you installed, and any installed package can already run
  arbitrary code, so the atlas is no trust boundary and adds no attack surface.
  Two honest facts remain: `guides` reads a guide from the package's files
  *without importing it*, and the entry point keeps unrelated packages' stray
  files out. The 0.4.x trust file, quarantine and `--prune` are gone; commit
  `.nexus-kit/` so it travels with the repo.
- **Editor-neutral, never writes your agent files.** `nexus-kit new` scaffolds a
  single `AGENTS.md` (the standard convention, no Claude/editor specifics) that
  mounts the map, plus a placeholder `.nexus-kit/map.md` so the mount is not
  dangling before the first run; otherwise the command only prints the mount hint.
- **`nexus-kit guides --check`** for CI: fails if `.nexus-kit/` is out of date,
  writes nothing.
- **One-shot migration**: `guides` removes the 0.4.x layout it finds (generated
  `.ai/*.md`, `trusted-guides.txt`, `.nexus-kit-quarantine/`); your own
  unstamped `.ai/` files are left alone. Update your mount from `.ai/` to
  `.nexus-kit/map.md`.
- Removed the `--trust` and `--prune` flags (no longer meaningful).

## [0.4.14] — 2026-07-21

Quarantine lifecycle finished (0.4.13's quarantine was half-built; both edges
reproduced before fixing):

- **`--prune` now empties the quarantine.** 0.4.13 moved a retired guide to
  `<name>.md.untrusted` and told you `--prune` would delete it — but cleanup
  only scanned `.ai/*.md`, so the renamed file was never found again and
  `--prune` was a no-op on it. Quarantined guides are now deleted for real.
- **Quarantine moved OUT of `.ai/`.** A guide kept inside `.ai/` (even as
  `*.md.untrusted`) is still reachable by an agent told to read the guides
  under `.ai/`. Retired guides now go to `.nexus-kit-quarantine/` at the app
  root — outside the tree the assistant is pointed at. A `<name>.md.untrusted`
  left by 0.4.13 is migrated there automatically; the scaffold gitignores the
  new directory.

Not a bug, restated for the record: with a global CLI whose version differs
from the app's kernel, the cheat-sheet body is still the CLI's (only the pin
and an in-band WARNING are the app's) — running via `uv run nexus-kit sync-ai`
remains the way to get a body that matches too. This is inherent: a 0.4.14 CLI
cannot reconstruct another version's guide.

## [0.4.13] — 2026-07-21

Third `sync-ai` hardening round; the CLI parser replaced wholesale. Each
finding reproduced before fixing.

- **A version-mismatch warning now lands IN the cheat sheet, not only on
  stdout.** When a global CLI writes an app whose kernel differs, the pin is
  the app's (correct) but the body is unavoidably the CLI's template — it may
  describe features the app's kernel lacks. The file now carries a `WARNING`
  comment saying so, so an agent reading it later is told, not just whoever
  watched the terminal.
- **Guides we no longer mirror are quarantined, not left in place.** A
  satellite guide that is uninstalled — or installed but no longer trusted
  (e.g. auto-mirrored by 0.4.10/0.4.11 before the trust gate) — used to be
  merely flagged "stale" while staying in `.ai/*.md`, where the assistant kept
  reading it. It is now moved to `<name>.md.untrusted` (out of the read path)
  by default; `--prune` deletes it for real. No guide is ever deleted silently.
- **Real argument parser.** The hand-rolled flag scan is replaced by
  `argparse` subcommands: unknown flags, stray positionals, a bare `--trust`
  with no package, and a missing `new <app-name>` are all rejected with a
  usage message instead of being silently accepted.
- **`build --env` with neither `.env` nor `.env.example` no longer lies.** It
  used to announce a fallback that shipped nothing; it now states plainly that
  `dist/` ships without a config template.

## [0.4.12] — 2026-07-20

Second `sync-ai` hardening round (an external review found the edges 0.4.11
left open; each reproduced before fixing):

- **The kernel version pin comes from the app, not the CLI.** A global
  `nexus-kit` wrote its own version into `~=` even when the app pinned a
  different kernel — satellites were read from the app venv but the kernel
  version was `version("nexus-kit")` of the interpreter running the CLI.
  The pin is now read from the nexus-kit installed in the app's `.venv`; a
  version mismatch with the CLI is reported, and only the cheat-sheet body
  (not the load-bearing pin) still reflects the CLI.
- **A satellite guide is mirrored only after you trust its package.** The
  `nexus-kit-*` name filter stops accidental/transitive guides but is not a
  trust boundary — anyone can publish `nexus-kit-evil`, and a guide is
  instructions an AI assistant will follow. Satellites are now opt-in:
  `nexus-kit sync-ai --trust <pkg>` records consent in
  `.ai/trusted-guides.txt` (the kernel is trusted implicitly); untrusted
  packages are listed, not written.
- **A customized legacy cheat sheet is preserved on migration.** Adopting
  an unstamped pre-0.4.10 `.ai/nexus-kit.md` now keeps the previous content
  as `.ai/nexus-kit.md.orig` before overwriting, so user edits are never
  lost silently.

## [0.4.11] — 2026-07-18

Hardening pass on `sync-ai` after an external review reproduced three design
holes in 0.4.10 (each reproduced here before fixing):

- **Scans the application environment, not the CLI's interpreter.** A
  `nexus-kit` installed as a global `uv tool` used to introspect its own
  isolated env — it saw no satellites and then "removed" every guide as
  uninstalled; the project's `uv run` recreated them (a delete/recreate
  ping-pong). sync-ai now discovers packages in the app's `.venv` beside
  `main.py`, so the global tool and `uv run` agree.
- **Only mirrors the `nexus-kit-*` namespace.** Discovery accepted a
  `.ai/guide.md` from ANY installed distribution — a transitive dependency
  (or a squatter) shipping one had a write channel straight into files an
  AI assistant reads. That is prompt injection; guides outside the
  namespace are now ignored.
- **Never deletes without `--prune`.** A plain run only creates/updates;
  removing the guide of an uninstalled package is now an explicit opt-in,
  so a mis-detected environment can never silently wipe correct files.
- **Migrates the legacy kernel cheat sheet.** A pre-0.4.10
  `.ai/nexus-kit.md` (no stamp) was treated as user-owned and left stale;
  the known generated header is now recognized, adopted and refreshed.
- `build`/`sync-ai` reject unknown flags instead of silently ignoring them;
  `build --env` with no `.env` now warns and ships `.env.example` (0.4.10
  left `dist/` with no config template at all).

## [0.4.10] — 2026-07-18

- **`nexus-kit sync-ai`** — installed satellites now reach the app's AI
  docs. pip/uv have no post-install hooks, so a freshly installed
  satellite could never announce itself to `CLAUDE.md`/`.ai/`. The new
  command mirrors the AI guide every satellite ships inside its wheel
  (`<package>/.ai/guide.md`) into the app's `.ai/<dist-name>.md`, refreshes
  the kernel cheat sheet to the installed version (previously it silently
  went stale after upgrades), and removes guides of uninstalled packages.
  Managed files carry a header stamp; unstamped `.ai/*.md` files are
  user-owned and never touched.
- Scaffolded `CLAUDE.md` now points at the `.ai/` directory (not one
  file) and names the sync-ai ritual — installing a satellite no longer
  requires editing `CLAUDE.md` at all. The cheat sheet documents the
  same ritual, so an AI assistant that installs a satellite fetches its
  own documentation for the next step.

## [0.4.9] — 2026-07-18

- **Scaffolded `main.py` survives windowed builds.** `faulthandler.enable()`
  was unconditional, but PyInstaller windowed apps (`console=False`) run
  with `sys.stderr = None` — the generated app died on its own first line.
  The scaffold now guards it (`if sys.stderr is not None`), and CI builds
  and runs a windowed executable on Windows so it stays true.
- The `4 - Beta` classifier actually reaches PyPI: 0.4.8 was published from
  a commit made before the classifier change (a tag/commit ordering slip),
  so its PyPI page still said Alpha.

## [0.4.8] — 2026-07-18

- Scaffold generates `.env.example` alongside `.env` — so the default
  (secret-free) `nexus-kit build` has an operator template to ship without
  the user hand-creating one.
- Docs honesty pass on the deployment story: "Deployment is an artifact,
  not a pipeline" — `dist/` is an executable plus its config (never "one
  file"), `--env` is called out as shipping real secrets, and the scope is
  stated plainly: handover distribution, not fleet management (no signing,
  no auto-updates, per-OS builds).

## [0.4.7] — 2026-07-17

- **`nexus-kit build`** replaces the generated `build.bat`/`build.sh` —
  building is a CLI command now: one Python implementation on every
  platform instead of two shell dialects to keep in sync. Cleans
  `build/`+`dist/`, runs PyInstaller, copies EXTERNAL files next to the
  binary.
- **Secrets no longer ship by default**: `build` copies `.env.example` as
  an operator template; the real `.env` goes into `dist/` only with an
  explicit `nexus-kit build --env` (appliance-style deploys).
- **PyInstaller is pinned**: the venv's own install wins (add it to your
  dev group — `uv.lock` then pins it exactly); the zero-setup fallback
  uses `uv run --with "pyinstaller>=6,<7"` instead of an unpinned latest.
- `freeze` now generates only `app.spec`.
- CI: the frozen-build job now runs on Windows, Linux **and macOS** — the
  cross-platform claim is machine-proven, not aspirational. Docs speak of
  "the executable", not "the exe".

## [0.4.6] — 2026-07-17

- **`nexus-kit freeze`** — the packaging story. Run from the app root:
  generates `app.spec` (with a `BUNDLED` list mirroring `Root.internal`),
  `build.bat` + `build.sh` (clean PyInstaller build, then EXTERNAL files —
  `.env`, `resources/` — copied next to the exe, where `Root.external`
  looks), and fixes `.gitignore` (`dist/`, `build/`; removes a legacy
  `*.spec` ignore — the spec is source). Existing files are never
  overwritten; `build.sh` is written LF-only even on Windows.
- Scaffold `.gitignore` no longer ignores `*.spec`.
- CI `frozen` job now builds through the shipped tooling (freeze + the
  generated spec) instead of a hand-rolled pyinstaller command.
- README: "Freezing your app" section; the generated AI cheat sheet gains
  a Freezing section.

## [0.4.5] — 2026-07-17

- Docs only: product-neutral wording for the donor applications on the
  PyPI page (no brand names in the framework's own story).

## [0.4.4] — 2026-07-17

- **ServiceRunner**: a cancellation arriving during the emergency cleanup of
  a failed `start()` now wins over the original startup error — previously
  it was swallowed and the start error escaped instead of `CancelledError`,
  breaking the asyncio contract (resources did not leak; the semantics did).
- Scaffold: the generated AI cheat sheet listed `Root` under import `nexus`
  instead of `nexus_kit`.
- CI: ruff lint job (8 findings fixed across the workspace) and a real
  PyInstaller freeze test on Windows — scaffold, build `--onefile`, run the
  exe with `.env` placed next to it, assert the config loads and the
  lifecycle stops cleanly.

## [0.4.3] — 2026-07-17

- **ServiceRunner**: a service whose `start()` fails now gets its own
  best-effort `stop()` before the rollback of already-started services —
  `start()` that opened a resource and then raised no longer leaks it.
  Write `stop()` to tolerate partially initialized state.
- Docs: the `stop_grace` guarantee is stated precisely — it bounds **async**
  stops only; a sync `stop()` runs inline unbounded (deliberate: a thread
  offload would break thread-affine teardown such as Qt).
- Security: `pydantic-settings` floor raised to 2.14.2
  (GHSA-4xgf-cpjx-pc3j — `secrets_dir` symlink traversal in 2.12.0–2.14.1).
- Changelog resurrected (was stuck at 0.1.1).

## [0.4.2] — 2026-07-16

- PyPI page links to GitHub: `project.urls` (Homepage, Repository, Issues,
  Changelog) + a Source/Issues/Releases row in the README.

## [0.4.1] — 2026-07-16

- README branded as nexus-kit with the standard badge row (PyPI version,
  Python versions, CI, license).

## [0.4.0] — 2026-07-16

- **First PyPI release**: `pip install nexus-kit`.
- **Breaking**: import package renamed `nexus` → `nexus_kit`; CLI command
  renamed `nexus` → `nexus-kit`. One name everywhere.
- Scaffold: plain `nexus-kit~=X.Y.Z` dependency instead of a git URL; the
  `allow-direct-references` hatch hack is gone.
- Publishing: GitHub Actions + PyPI trusted publishing (OIDC), triggered by
  version tags.

## [0.3.3] — 2026-07-16

- Scaffold quickstart fixed: generated projects failed `uv sync` (hatchling
  rejects direct git references without `allow-direct-references`).
- Scaffold now generates `.gitignore` (`.env`, `.venv/`, `__pycache__/`, …).
- **ServiceRunner**: DI resolution failure mid-startup now rolls back the
  already-started services; task cancellation during teardown no longer
  abandons the remaining stops.
- Test suite (runner contracts, env loading, Root anchoring, scaffold e2e)
  and CI (ubuntu + windows × Python 3.12/3.13/3.14).

## [0.3.2] — 2026-07-16

- Scaffold example replaced with the target-audience skeleton: a `Ticker`
  worker thread (stop Event + bounded join) reporting through an injected
  `ReporterInterface` seam.

## [0.3.1] — 2026-07-16

- Scaffold demonstrates the lifecycle: the generated app runs its services
  under `ServiceRunner`.

## [0.3.0] — 2026-07-16

- **Service lifecycle**: `ServiceInterface` (`start()`/`stop()`, sync or
  async) + `ServiceRunner` — ordered start, guaranteed reverse-order stop,
  crash-safe startup, `stop_grace` for async stops, no signal grabbing.

## [0.2.0] — 2026-07-16

- **Breaking**: optional extras removed; `injector` and `pydantic-settings`
  are core dependencies (fixes `import nexus` crashing without the
  `[pydantic]` extra).
- `requires-python` lowered to 3.12.
- Scaffold pins the framework version instead of tracking master.
- `EnvironmentInterface` defaults: `env_file_encoding="utf-8-sig"` (BOM
  tolerance), `extra="ignore"` (foreign keys in shared `.env` files).
- `Root` dev paths anchor to the entry script's directory instead of cwd.

## [0.1.1]

### Added

- `nexus.logging` — DI-injectable logging base (`NamedLogger`, `StdoutHandler`, `LogFormatter`).
- `nexus new <app-name>` scaffolds an AI-ready project: `CLAUDE.md` pointing to `.ai/`,
  and a compact self-contained framework reference for AI assistants.

### Changed

- Refreshed `.ai/guide.md` (AI Agent Guide).

## [0.1.0] — 2025-07-02

Initial release.

### Added

- `ApplicationInterface` — abstract contract for application bootstrap
- `ContainerInterface` — abstract contract for dependency injection container
- `EnvironmentInterface` — abstract base for typed configuration (Pydantic BaseSettings + singleton)
- `Root` — path utility for development and PyInstaller-bundled environments
- `ContainerInjector` — `ContainerInterface` implementation using the `injector` library
- `nexus new <app-name>` CLI command to scaffold a minimal working application

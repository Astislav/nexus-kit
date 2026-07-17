# Changelog

All notable changes to nexus-kit. Versioning: [semver](https://semver.org/) —
in 0.x, breaking changes bump the minor version.

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

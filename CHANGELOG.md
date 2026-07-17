# Changelog

All notable changes to nexus-kit. Versioning: [semver](https://semver.org/) —
in 0.x, breaking changes bump the minor version.

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

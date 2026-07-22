# nexus-kit

[![PyPI](https://img.shields.io/pypi/v/nexus-kit)](https://pypi.org/project/nexus-kit/)
[![CI](https://github.com/Astislav/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/Astislav/nexus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A minimal application kernel for long-lived Python apps: one entry point,
typed config, constructor DI, logger channels, service lifecycle — and a
deploy story that fits in a single artifact.

```python
# ---- your fifth app, today --------------------------------------
# config.py of module-level globals, mutated at import time
# logging configured in three places, differently
# shutdown = atexit + __del__ + hope
# if hasattr(sys, "_MEIPASS"): ...   copy-pasted around every resource
# deploy = "works on my machine" and a README nobody follows

# ---- your fifth app, on nexus-kit -------------------------------
env = Environment(Root.external(".env"))   # typed config, .env-aware
container = ContainerInjector(DI_CONFIG)   # DI: one dict, no magic
container.set(Environment, env)
Application(env, container).run()          # services start in order,
                                           # stop in reverse — guaranteed
```

## The problem nobody names

Web apps have frameworks. **Applications don't.** Django owns the request
cycle, FastAPI owns the endpoint — but a Qt tool driving hardware, a
pygame game, a Windows daemon, a process where HTTP is just one concern
among sockets, workers and a device fleet? No-man's land. Every such
program reinvents its own bootstrap, config story and shutdown
choreography — all the same, all slightly broken.

nexus-kit is that missing layer. Every app gets the same shape: `main.py`
is four lines, config is a typed class, services declare dependencies in
constructors, long-lived services start in order and stop in reverse —
guaranteed, including on Ctrl+C. Your fifth app looks like your first,
and anyone — human or AI — who has seen one has seen them all.

## Who it's for

- You ship Python as **PyInstaller executables** and are tired of path
  bugs that only appear after freezing.
- You maintain **several apps** — web and not — and want them all shaped
  the same instead of each inventing its own bootstrap.
- You want **constructor injection without magic**: one explicit
  `{Interface: Implementation}` dict, no string keys, no globals, no
  auto-scanning.
- Your app has **services that must start in order and stop cleanly** —
  DB pools, pollers, device monitors, an embedded HTTP server.

## Who it's NOT for

- **Short scripts.** A module with functions is already dependency
  injection. This would be ceremony.
- **Apps living happily inside FastAPI/Django conventions.** Their
  lifespan and DI are enough; nexus-kit solves the world outside that
  cradle.
- **Teams that want a mainstream stack.** This is an opinionated kernel:
  conventions over ecosystem, no Stack Overflow answers.

## What it is, honestly

Opinionated glue — not invention. Config is stock
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
DI is stock [injector](https://injector.readthedocs.io/); nexus-kit adds
the parts nobody packages: the `Root` path resolver for frozen builds,
typed logger channels, the `ServiceRunner` lifecycle, a scaffolder, and
the convention that ties them together. Extracted from real production
apps (a Qt hardware-control desk, a messaging gateway, forensic analytics
services), not designed in a vacuum.

## From zero to a shipped executable

```bash
uv tool install nexus-kit      # or: uv add nexus-kit in an existing project

nexus-kit new my-app           # scaffold: typed config, DI, lifecycle demo
cd my-app && uv sync
python main.py                 # a worker ticks, stops cleanly — the whole shape

nexus-kit freeze               # once: generate app.spec (PyInstaller)
nexus-kit build                # every release: clean build → dist/my-app  (.exe on Windows)
```

Same commands on Windows, Linux and macOS — no `.bat`/`.sh` to keep in
sync. Bundled assets live inside the executable (`Root.internal`), operator files
land next to it (`Root.external`). The full path — scaffold → freeze →
build → run the executable — is exercised by CI on Windows, Linux and macOS on every push.

## Deployment is an artifact, not a pipeline

There is a class of software the industry pretends not to see: the
internal automation you — or your AI assistant — built in an afternoon.
A parser, a report bot, a device controller. You don't know yet whether
the team will adopt it. The correct amount of deployment infrastructure
for that bet is **zero**: no Dockerfile, no registry, no pipeline, no
YAML.

```bash
nexus-kit build --env    # dist/: the executable + its config, ready to hand over
```

Zip `dist/`, drop it in the chat, done — the person running it needs
Python installed exactly as much as they need your k8s cluster: not at
all. (`--env` ships your real secrets — use it for machines you'd trust
with them anyway; the default ships `.env.example` for the operator to
fill in.) If the tool takes root, you graduate deliberately: PyInstaller
pins into your dev group, CI arrives when it's earned. If the tool dies —
you delete a folder, not a deployment.

Call it what it is: **handover distribution, not fleet management**. No
code signing, no auto-updates, no rollback — and PyInstaller builds are
per-OS, so build on the platform you target. That's the point: those
things arrive when the tool has earned them, not before. For unproven
software this is the superior strategy — and in the AI era, where writing
the tool costs an afternoon, **distribution is the bottleneck**.
nexus-kit makes distribution a build artifact.

## “Is this even pythonic?” — an honest answer

**“This looks like Java.”** Partially guilty. `GreeterInterface` is
nominal typing; current Python fashion is structural (`Protocol`). We
chose ABCs deliberately: the contract is visible at the declaration, and
violations fail when the container builds the graph — not at 3 a.m. when
the frozen executable on someone else's machine first hits the missing method.

Now check what the actual Zen says: *explicit is better than implicit*.
One `DI_CONFIG` dict you can read. A `SERVICES` list that *is* the
startup order. No decorator scanning, no string keys, no import-time
side effects, no metaclasses. nexus-kit breaks Python **fashion**, not
Python **philosophy** — plenty of "pythonic" frameworks resolve your
dependencies by magic and call it elegance.

And if a module with functions covers your needs — it genuinely is the
better tool; close the tab, no hard feelings. This kernel is for the day
your functions grow threads, sockets and a shutdown order.

## Your AI assistant already knows this framework

Every package in this repo carries a machine-oriented
[`.ai/guide.md`](nexus-kit/.ai/guide.md) — API contract, conventions,
anti-patterns — updated **in the same commit** as the API it describes, and
shipped **inside the wheel**. In a consumer app, `uv run nexus-kit guides`
discovers every installed nexus-kit package (via a declared entry point) and
writes an **atlas** into `.nexus-kit/`: a small always-on `map.md` — indexed
with a *read-this-when* cue per package — plus one on-demand guide each. You
mount just the map in your own AGENTS.md; the agent opens a specific guide when
it's relevant, so ten satellites don't bloat the context. It's plain markdown and
the standard AGENTS.md convention — no editor lock-in — and the tooling never
edits your AGENTS.md. (No security theatre either: a guide is just docs from a
package you installed, and an installed package can already run code, so vet your
dependencies as you would any code; the atlas adds no attack surface.) Frameworks
used to be documented for humans; this one is documented for the pair of you.

## Principles

- **No string keys.** If you can grep it by type, you can refactor it.
- **No magic.** The composition root is a dict you read top to bottom.
- **Stop in reverse order, guaranteed** — on return, exception, Ctrl+C.
- **Secrets don't ship.** Your `.env` enters `dist/` only via an explicit
  `--env`.
- **The core grabs no signals.** Exit is the application's decision.
- **Deployment is an artifact, not a pipeline** — a feature, not an
  apology.
- **Extracted, not designed.** Every satellite is cut out of a running
  production app; nothing here was invented on a whiteboard.
- **Stale AI docs are worse than none.** The machine guide changes in the
  same commit as the API.

## Packages

This is a uv-workspace monorepo; each directory is an independently
versioned PyPI distribution.

| Package | PyPI | What it is |
|---------|------|------------|
| [`nexus-kit`](nexus-kit/) | [![PyPI](https://img.shields.io/pypi/v/nexus-kit)](https://pypi.org/project/nexus-kit/) | The kernel: entry point, typed config, DI, logger channels, service lifecycle, PyInstaller-safe paths, `new`/`freeze`/`build` CLI |
| [`nexus-kit-fastapi`](nexus-kit-fastapi/) | [![PyPI](https://img.shields.io/pypi/v/nexus-kit-fastapi)](https://pypi.org/project/nexus-kit-fastapi/) | FastAPI + uvicorn as a lifecycle service, `Injected(cls)` Depends bridge into the container |

Satellites are extracted from real apps as they migrate — next up:
`nexus-kit-postgres` (asyncpg pool as a lifecycle service).

**Full kernel documentation → [nexus-kit/README.md](nexus-kit/README.md)**
(environment, DI, lifecycle guarantees, logging, paths, freezing).

## Development

```bash
uv sync --all-packages   # one shared venv for every package in the workspace
uv run pytest            # run every package's tests
uv run ruff check .
```

Releases are tag-driven: `v1.2.3` publishes `nexus-kit`;
`<name>-v1.2.3` publishes `nexus-kit-<name>`.

**New package checklist** — a directory beside the others, named after its
PyPI dist (dir = dist name = tag prefix), containing: `pyproject.toml`,
`src/<import_name>/`, `tests/`, `README.md` (with a *For AI assistants*
section), `CHANGELOG.md`, `LICENSE`, and **`.ai/guide.md`** — force-included
into the wheel as `<import_name>/.ai/guide.md` and declared via a
`[project.entry-points."nexus_kit.ai_guides"]` entry so `nexus-kit guides`
discovers it for the consumer app's `.nexus-kit/` atlas. Plus one pending
publisher on PyPI and a row in the table above.

**AI-guide discipline**: `.ai/guide.md` changes in the same commit as the
public API it describes — a stale machine guide is worse than none, an
agent will confidently build against a dead contract. Docs describe donor
apps by class (a gateway, an analytics service), never by product name.

**README split**: audience and philosophy text (why / who for / pythonic)
lives ONLY in this root README; package READMEs are references and carry
a one-paragraph audience distillation plus a link here — duplicated pitch
text drifts.

## License

MIT © Astislav Bozhevolnov

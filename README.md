# nexus — the nexus-kit workspace

[![CI](https://github.com/Astislav/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/Astislav/nexus/actions/workflows/ci.yml)

Monorepo for **nexus-kit** — a minimal application kernel for long-lived
Python apps — and its satellite packages. Each directory below is an
independently versioned and published PyPI distribution.

| Package | PyPI | What it is |
|---------|------|------------|
| [`nexus-kit`](nexus-kit/) | [![PyPI](https://img.shields.io/pypi/v/nexus-kit)](https://pypi.org/project/nexus-kit/) | The kernel: entry point, typed config, DI, logger channels, service lifecycle, PyInstaller-safe paths |

Satellites (planned, extracted from real apps as they migrate):
`nexus-kit-postgres` (asyncpg pool as a lifecycle service),
`nexus-kit-fastapi` (uvicorn as a lifecycle service).

**Start here → [nexus-kit/README.md](nexus-kit/README.md)** — the full
framework documentation.

## Development

```bash
uv sync --all-packages   # one shared venv for every package in the workspace
uv run pytest            # run every package's tests
```

Releases are tag-driven: `v1.2.3` publishes `nexus-kit`;
`<name>-v1.2.3` publishes `nexus-kit-<name>`.

## License

MIT © Astislav Bozhevolnov

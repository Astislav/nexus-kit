# nexus-kit-fastapi

[![PyPI](https://img.shields.io/pypi/v/nexus-kit-fastapi)](https://pypi.org/project/nexus-kit-fastapi/)
[![CI](https://github.com/Astislav/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/Astislav/nexus/actions/workflows/ci.yml)

FastAPI + uvicorn as a [nexus-kit](https://pypi.org/project/nexus-kit/)
lifecycle service, plus a `Depends` bridge into the nexus container.

A **bridge, not a wrapper**: FastAPI stays fully in charge of HTTP —
routers, middleware, auth, OpenAPI are plain FastAPI. This package owns
only the process concerns: when the server starts and stops (as one
`ServiceInterface` among your other services), and how route handlers
reach the nexus container.

```bash
uv add nexus-kit-fastapi
```

## The server as a service

```python
# app/api/service.py
from injector import inject, singleton
from fastapi import FastAPI
from nexus_kit.interfaces import ContainerInterface
from nexus_kit_fastapi import HttpService

from app.config.environment import Environment
from app.api import accounts, health

@singleton
class ApiService(HttpService):
    @inject
    def __init__(self, env: Environment, container: ContainerInterface) -> None:
        super().__init__(container)
        self.host, self.port = env.HOST, env.PORT

    def create_app(self) -> FastAPI:          # plain FastAPI — yours entirely
        app = FastAPI(title="my gateway")
        app.include_router(health.router)
        app.include_router(accounts.router)
        return app
```

```python
# app/application.py
class Application(ApplicationInterface):
    SERVICES = [Database, WebhookDispatcher, ApiService]   # http last up, first down

    async def _serve(self) -> None:
        async with ServiceRunner(self._container, self.SERVICES):
            await self._container.get(ApiService).wait()   # until Ctrl+C / SIGTERM
```

`start()` returns only once the socket is bound — a busy port raises right
there and `ServiceRunner` rolls the other services back. `stop()` is a
graceful uvicorn shutdown. `port = 0` binds an ephemeral port
(`service.bound_port` tells which — handy in tests).

## Routes reach the container through plain `Depends`

`Injected(cls)` is an ordinary FastAPI dependency that resolves `cls` from
the container — no per-service `get_x()` boilerplate:

```python
from nexus_kit_fastapi import Injected

@router.post("/send")
async def send(text: str, sender: Sender = Injected(Sender)):
    await sender.enqueue(text)
```

It composes with everything FastAPI: auth dependencies, sub-dependencies,
`Annotated`, middleware. For tests, bind fakes into the container
(`container.set(Sender, FakeSender())`) and drive the app with FastAPI's
`TestClient` — attach the container manually via `attach_container(app,
container)`, no server needed.

## Signals

The bridge handles SIGINT/SIGTERM (and SIGBREAK on Windows) itself and
converts them into a graceful drain: `wait()` returns, your Application
body exits, `ServiceRunner` stops every service, the process ends normally.
A second signal skips the drain and goes down hard.

Why not leave it to uvicorn: uvicorn's stock signal capture restores the
*previous* handlers after its own shutdown and **re-raises the captured
signal** — with default handlers a SIGTERM kills the process before the
rest of your services get their `stop()`. In a composite app that breaks
the whole teardown promise, so the bridge disables uvicorn's capture and
owns the conversion. Set `handle_signals = False` on your subclass if the
application manages signals itself. The nexus core remains signal-free.

## What this package deliberately does NOT do

- No FastAPI lifespan management — your `Application` + `ServiceRunner`
  own the lifecycle; the HTTP edge is just one service among many.
- No routing/middleware/auth helpers — that's FastAPI's job.

## For AI assistants

The package ships a compact machine-oriented reference —
[`.ai/guide.md`](https://github.com/Astislav/nexus/blob/master/nexus-kit-fastapi/.ai/guide.md):
the HttpService contract, the `Injected` bridge, and the anti-patterns to
avoid. Point your agent at it before it touches the HTTP layer.

The guide also ships inside the wheel: after installing this package, run
`uv run nexus-kit sync-ai` from your app root and it lands in your app's
`.ai/nexus-kit-fastapi.md`, where your assistant reads it automatically.

## License

MIT © Astislav Bozhevolnov

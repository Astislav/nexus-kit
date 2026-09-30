"""Bridge between FastAPI's dependency system and the nexus container.

FastAPI's `Depends` stays the one idiom in route signatures. `Injected(cls)`
is just a `Depends` that resolves `cls` from the container attached to the
app — a plain FastAPI dependency, nothing more, so it composes with auth
dependencies, sub-dependencies and middleware exactly like any other.

For tests, bind fakes into the container (`container.set(Interface, fake)`)
or attach a test container to the app with `attach_container` and use
FastAPI's TestClient — no server needed.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from starlette.requests import HTTPConnection

from nexus_kit.interfaces import ContainerInterface

_STATE_ATTR = "nexus_container"


def attach_container(app: FastAPI, container: ContainerInterface) -> None:
    """Hand the nexus container to a FastAPI app.

    HttpService.start() does this for you; call it manually only for
    TestClient setups or externally-managed apps.
    """
    setattr(app.state, _STATE_ATTR, container)


def get_container(connection: HTTPConnection) -> ContainerInterface:
    """The nexus container of the current app — for hand-written dependencies.

    Takes the Starlette HTTPConnection (the base of both Request and
    WebSocket), so it works in HTTP and WebSocket dependencies alike. For a
    mounted sub-app, attach the container to the sub-app too — `request.app`
    is the innermost app.
    """
    container = getattr(connection.app.state, _STATE_ATTR, None)
    if container is None:
        raise HTTPException(status_code=503, detail="nexus container is not attached to this app")
    return container


def Injected[T](cls: type[T]) -> T:  # noqa: N802 — deliberately reads like FastAPI's Depends
    """A `Depends(...)` that resolves `cls` from the nexus container.

    The return type is a deliberate lie (the value is a Depends marker) —
    the same lie FastAPI's own Depends idiom lives by: it makes
    `greeter: Greeter = Injected(Greeter)` type-check, so IDEs and mypy treat
    the parameter as a real Greeter. The precise typing mirrors
    ContainerInterface.get(cls: type[T]) -> T, which this marker adapts
    into FastAPI's dependency slot.

        @router.get("/greet")
        async def greet(name: str, greeter: Greeter = Injected(Greeter)) -> dict[str, str]:
            return {"message": greeter.greet(name)}
    """

    # async on purpose: a sync dependency would be shipped to FastAPI's
    # threadpool on every request — a pointless hop for a dict lookup.
    async def resolve(connection: HTTPConnection):
        return get_container(connection).get(cls)

    resolve.__name__ = f"injected_{getattr(cls, '__name__', cls)}"
    return Depends(resolve)

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

from fastapi import Depends, FastAPI, HTTPException, Request

from nexus_kit.interfaces import ContainerInterface

_STATE_ATTR = "nexus_container"


def attach_container(app: FastAPI, container: ContainerInterface) -> None:
    """Hand the nexus container to a FastAPI app.

    HttpService.start() does this for you; call it manually only for
    TestClient setups or externally-managed apps.
    """
    setattr(app.state, _STATE_ATTR, container)


def get_container(request: Request) -> ContainerInterface:
    """The nexus container of the current app — for hand-written dependencies."""
    container = getattr(request.app.state, _STATE_ATTR, None)
    if container is None:
        raise HTTPException(status_code=503, detail="nexus container is not attached to this app")
    return container


def Injected(cls):  # noqa: N802 — deliberately reads like FastAPI's Depends
    """A `Depends(...)` that resolves `cls` from the nexus container.

        @router.post("/send")
        async def send(text: str, sender: Sender = Injected(Sender)) -> None:
            await sender.enqueue(text)
    """

    def resolve(request: Request):
        return get_container(request).get(cls)

    resolve.__name__ = f"injected_{getattr(cls, '__name__', cls)}"
    return Depends(resolve)

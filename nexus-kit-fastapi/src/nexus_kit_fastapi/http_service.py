"""uvicorn as a nexus lifecycle service — a bridge, not a wrapper.

FastAPI stays fully in charge of HTTP: you build the app (routers,
middleware, auth, OpenAPI) with plain FastAPI idioms. This service owns
only the process concerns — when the server starts, when it stops, and how
route handlers reach the nexus container (see `inject.Injected`).

Deliberately NOT owned here: service lifecycle belongs to your Application
via ServiceRunner, not to a FastAPI lifespan — the HTTP edge is just one
service among many.
"""
from __future__ import annotations

import asyncio
import socket
from abc import abstractmethod
from typing import Optional

import uvicorn
from fastapi import FastAPI
from injector import inject

from nexus_kit.interfaces import ContainerInterface, ServiceInterface

from nexus_kit_fastapi.inject import attach_container


class HttpService(ServiceInterface):
    """Serve a FastAPI app as a nexus service.

    Subclass: implement `create_app()`, feed host/port from your Environment
    in an `@inject` constructor:

        @singleton
        class ApiService(HttpService):
            @inject
            def __init__(self, env: Environment, container: ContainerInterface) -> None:
                super().__init__(container)
                self.host, self.port = env.HOST, env.PORT

            def create_app(self) -> FastAPI:
                app = FastAPI(title="my api")
                app.include_router(my_router)
                return app

    Contract:
    - start() binds the socket itself, synchronously, then hands it to
      uvicorn — a busy port raises a plain OSError right in start(), so
      ServiceRunner can roll back cleanly (uvicorn's own bind path would
      sys.exit(3) inside the task instead);
    - stop() asks uvicorn for a graceful exit and awaits it; idempotent;
    - wait() blocks until the server exits (uvicorn handles Ctrl+C/SIGTERM
      itself when it runs in the main-thread event loop) — the natural body
      for an HTTP-fronted Application:

        async with ServiceRunner(self._container, self.SERVICES):
            await self._container.get(ApiService).wait()
    """

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    @inject
    def __init__(self, container: ContainerInterface) -> None:
        # @inject here means a subclass with no __init__ of its own is fully
        # container-constructible; subclasses that need Environment define
        # their own @inject __init__ and call super().__init__(container).
        self._container = container
        self._server: Optional[uvicorn.Server] = None
        self._task: Optional[asyncio.Task] = None
        self._socket: Optional[socket.socket] = None
        self._bound_port: Optional[int] = None

    @abstractmethod
    def create_app(self) -> FastAPI: ...

    def uvicorn_config(self, app: FastAPI) -> uvicorn.Config:
        """Override for TLS, proxy headers, custom log config — plain uvicorn API."""
        return uvicorn.Config(app, host=self.host, port=self.port, log_level=self.log_level)

    async def start(self) -> None:
        app = self.create_app()
        attach_container(app, self._container)
        config = self.uvicorn_config(app)
        self._server = uvicorn.Server(config)
        # Bind the socket ourselves, synchronously: a busy port surfaces right
        # here as a plain OSError — NOT uvicorn's in-task sys.exit(3), which
        # would blow through the event loop past any rollback. uvicorn's
        # bind_socket() also sys.exit()s on failure, but synchronously we can
        # catch and translate it.
        try:
            self._socket = config.bind_socket()
        except SystemExit as exc:
            self._reset()
            raise OSError(f"{type(self).__name__}: failed to bind {self.host}:{self.port}") from exc
        address = self._socket.getsockname()
        self._bound_port = address[1] if isinstance(address, tuple) else None
        self._task = asyncio.create_task(
            self._server.serve(sockets=[self._socket]), name=f"{type(self).__name__}-serve"
        )
        while not self._server.started and not self._task.done():
            await asyncio.sleep(0.01)
        if self._task.done():
            task = self._task
            self._reset()
            await task  # re-raises the startup failure (bad TLS, broken app, ...)
            raise RuntimeError(f"{type(self).__name__}: uvicorn exited during startup")

    async def wait(self) -> None:
        """Block until the server exits."""
        if self._task is not None:
            await self._task

    async def stop(self) -> None:  # idempotent
        server, task, sock = self._server, self._task, self._socket
        self._reset()
        if server is not None:
            server.should_exit = True
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass
        if sock is not None:
            sock.close()

    def _reset(self) -> None:
        self._server = None
        self._task = None
        self._socket = None
        self._bound_port = None

    @property
    def bound_port(self) -> int:
        """The actually bound port — useful with port=0 (tests, parallel apps)."""
        if self._bound_port is None:
            raise RuntimeError("server is not started")
        return self._bound_port

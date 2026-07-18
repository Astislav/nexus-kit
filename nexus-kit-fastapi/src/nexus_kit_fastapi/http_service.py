"""uvicorn as a nexus lifecycle service — a bridge, not a wrapper.

FastAPI stays fully in charge of HTTP: you build the app (routers,
middleware, auth, OpenAPI) with plain FastAPI idioms. This service owns
only the process concerns — when the server starts, when it stops, and how
route handlers reach the nexus container (see `inject.Injected`).

Deliberately NOT owned here: service lifecycle belongs to your Application
via ServiceRunner, not to a FastAPI lifespan — the HTTP edge is just one
service among many.

Signals: unlike a bare uvicorn, this bridge handles them itself (opt-out
via `handle_signals = False`). uvicorn's own capture is disabled because it
restores the previous handlers and RE-RAISES the captured signal after its
shutdown — with default handlers a SIGTERM would kill the process before
ServiceRunner finishes stopping the other services. The bridge converts
SIGINT/SIGTERM (and SIGBREAK on Windows) into a graceful drain instead:
wait() returns, the Application body exits, the runner tears everything
down, the process ends normally.
"""
from __future__ import annotations

import asyncio
import contextlib
import signal
import socket
import sys
import threading
from abc import abstractmethod
from collections.abc import Generator
from typing import Optional

import uvicorn
from fastapi import FastAPI
from injector import inject

from nexus_kit.interfaces import ContainerInterface, ServiceInterface

from nexus_kit_fastapi.inject import attach_container


class _QuietServer(uvicorn.Server):
    """uvicorn.Server with its signal handling disabled.

    Stock uvicorn installs SIGINT/SIGTERM handlers and, after a graceful
    shutdown, restores the ORIGINAL handlers and re-raises the captured
    signal (`capture_signals`). In a composite app that re-raise arrives
    when the default handler is back in charge and terminates the process
    mid-teardown. HttpService owns the signals instead.
    """

    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None, None, None]:  # uvicorn >= 0.29
        yield

    def install_signal_handlers(self) -> None:  # older uvicorn code path
        pass


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
    - start() binds the socket itself, synchronously — a busy port raises a
      plain OSError right in start(), so ServiceRunner can roll back cleanly;
      uvicorn's in-task sys.exit()s (e.g. a failed FastAPI lifespan) are
      translated into a normal RuntimeError for the same reason. Cancelling
      a still-starting start() tears everything down (serve task, socket,
      signal handlers); calling start() on a started service raises.
    - stop() is a graceful uvicorn shutdown, idempotent; a cancellation of
      the caller is honoured, not swallowed — and the port is released
      either way.
    - wait() blocks until the server exits — the natural Application body:
      `async with ServiceRunner(...): await container.get(ApiService).wait()`.
    - signals: handled by the bridge by default (`handle_signals = True`) —
      SIGINT/SIGTERM/SIGBREAK request a graceful drain, so wait() returns
      and the runner still stops every service. Set `handle_signals = False`
      if your application owns signal handling itself.
    - `port = 0` binds an ephemeral port; read it via `bound_port`.
    - Override `uvicorn_config(app)` for TLS/proxy headers, or to wrap the
      app in ASGI middleware (e.g. `socketio.ASGIApp`) before serving.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    handle_signals: bool = True

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
        self._signal_originals: dict[int, object] = {}

    @abstractmethod
    def create_app(self) -> FastAPI: ...

    def uvicorn_config(self, app: FastAPI) -> uvicorn.Config:
        """Override for TLS, proxy headers, custom log config — plain uvicorn API."""
        return uvicorn.Config(app, host=self.host, port=self.port, log_level=self.log_level)

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError(f"{type(self).__name__} is already started — stop() it first")
        app = self.create_app()
        attach_container(app, self._container)
        config = self.uvicorn_config(app)
        self._server = _QuietServer(config)
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
        if self.handle_signals:
            self._install_signal_handlers()
        self._task = asyncio.create_task(self._run_server(), name=f"{type(self).__name__}-serve")
        try:
            while not self._server.started and not self._task.done():
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            # Cancelled mid-startup (e.g. a bounded rollback around a hung
            # lifespan): leave nothing behind — no serve task, no signal
            # handlers, no bound port.
            task, sock = self._task, self._socket
            self._restore_signal_handlers()
            self._reset()
            task.cancel()
            try:
                with contextlib.suppress(BaseException):
                    await task
            finally:
                sock.close()
            raise
        if self._task.done():
            task, sock = self._task, self._socket
            self._restore_signal_handlers()
            self._reset()
            if sock is not None:
                sock.close()  # else the bound port lingers until GC and an in-process retry gets EADDRINUSE
            await task  # re-raises the startup failure as a normal exception
            raise RuntimeError(f"{type(self).__name__}: uvicorn exited during startup")

    async def _run_server(self) -> None:
        try:
            await self._server.serve(sockets=[self._socket])
        except SystemExit as exc:
            # uvicorn sys.exit()s inside the task on startup failures (e.g. a
            # failed FastAPI lifespan). SystemExit from a task blows straight
            # through the event loop, past every rollback — translate it.
            raise RuntimeError(
                f"{type(self).__name__}: uvicorn exited with code {exc.code} (failed lifespan startup?)"
            ) from exc

    async def wait(self) -> None:
        """Block until the server exits (graceful signal, stop(), or crash)."""
        if self._task is not None:
            await self._task

    async def stop(self) -> None:  # idempotent
        server, task, sock = self._server, self._task, self._socket
        self._restore_signal_handlers()
        self._reset()
        if server is not None:
            server.should_exit = True
        try:
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        # The cancellation targets US — honour it. Cancel the
                        # server task too so it doesn't linger, then re-raise.
                        task.cancel()
                        raise
                    # Otherwise the server task itself was cancelled: it is
                    # down, which is what stop() wanted.
        finally:
            # Even when the drain is cancelled (a ServiceRunner stop_grace
            # timeout takes exactly this path) the port must be released NOW,
            # not when the GC finds the socket.
            if sock is not None:
                sock.close()

    # --- signal handling (bridge-owned; see module docstring) ---

    def _handled_signals(self) -> list[signal.Signals]:
        sigs = [signal.SIGINT, signal.SIGTERM]
        if sys.platform == "win32":
            sigs.append(signal.SIGBREAK)
        return sigs

    def _request_exit(self) -> None:
        server = self._server
        if server is None:
            return
        if server.should_exit:
            server.force_exit = True  # second signal: stop draining, go down now
        else:
            server.should_exit = True

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return  # signals are a main-thread affair; embedded loops opt out naturally
        loop = asyncio.get_running_loop()

        # signal.signal on purpose, NOT loop.add_signal_handler: asyncio has no
        # API to read the loop's current handler, so a loop handler could never
        # be saved or restored — it would silently clobber whatever the
        # application installed. Plain signals save/restore cleanly on every
        # platform (the same reasoning uvicorn's own capture uses); the handler
        # fires in the main thread and hops into the loop thread-safely.
        def request_exit(sig: int, frame: object) -> None:
            loop.call_soon_threadsafe(self._request_exit)

        for sig in self._handled_signals():
            with contextlib.suppress(ValueError, OSError):
                self._signal_originals[sig] = signal.signal(sig, request_exit)

    def _restore_signal_handlers(self) -> None:
        for sig, previous in self._signal_originals.items():
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, previous)  # type: ignore[arg-type]
        self._signal_originals = {}

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

import asyncio
import inspect
import logging
from typing import Sequence, Type

from nexus_kit.interfaces.container import ContainerInterface
from nexus_kit.interfaces.service import ServiceInterface


class ServiceRunner:
    """Starts services in order, stops them in reverse — guaranteed.

    Sync app (pygame, Qt worker threads):

        runner = ServiceRunner(container, SERVICES)
        with runner:
            main_loop()

    Async app (asyncio servers):

        async with ServiceRunner(container, SERVICES) as runner:
            await http.wait()

    Startup is crash-safe: if the N-th service fails to start, that service's
    own stop() is still called (best-effort — start() may have opened
    resources before failing, so write stop() to tolerate partially
    initialized state), then the already started N-1 are stopped in reverse
    order and the error is re-raised. Teardown runs on any exit — normal
    return, exception, Ctrl+C — and keeps going past individual stop()
    failures (they are logged, not raised, so every service gets its chance
    to shut down).

    The runner does NOT install signal handlers: who triggers the exit is
    the application's business (uvicorn's own handlers, Qt's aboutToQuit,
    or your own). In the async context each ASYNC stop() is bounded by
    `stop_grace` seconds, then cancelled; a SYNC stop() runs inline and is
    not bounded — deliberately, because offloading it to a thread would
    silently break thread-affine teardown (Qt, COM). If the surrounding
    task is cancelled mid-teardown, the remaining services are still
    stopped before the cancellation is re-raised.
    """

    def __init__(
            self,
            container: ContainerInterface,
            services: Sequence[Type[ServiceInterface]],
            stop_grace: float = 10.0,
            logger: logging.Logger | None = None,
    ) -> None:
        self._container = container
        self._service_types = list(services)
        self._stop_grace = stop_grace
        self._log = logger or logging.getLogger("nexus.services")
        self._started: list[ServiceInterface] = []

    # --- sync context ---

    def __enter__(self) -> "ServiceRunner":
        for cls in self._service_types:
            try:
                service = self._container.get(cls)
                if inspect.iscoroutinefunction(service.start) or inspect.iscoroutinefunction(service.stop):
                    raise TypeError(f"{cls.__name__} is async — use 'async with' instead of 'with'")
            except BaseException:
                self.stop_all()
                raise
            try:
                service.start()
            except BaseException:
                self._stop_one(service)  # start() may have opened resources before failing
                self.stop_all()
                raise
            self._started.append(service)
            self._log.info("started %s", cls.__name__)
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop_all()

    def stop_all(self) -> None:
        while self._started:
            self._stop_one(self._started.pop())

    def _stop_one(self, service: ServiceInterface) -> None:
        try:
            service.stop()
            self._log.info("stopped %s", type(service).__name__)
        except Exception:
            self._log.exception("%s.stop() failed", type(service).__name__)

    # --- async context ---

    async def __aenter__(self) -> "ServiceRunner":
        for cls in self._service_types:
            try:
                service = self._container.get(cls)
            except BaseException:
                await self.stop_all_async()
                raise
            try:
                result = service.start()
                if inspect.isawaitable(result):
                    await result
            except BaseException:
                await self._stop_one_async(service)  # start() may have opened resources before failing
                await self.stop_all_async()
                raise
            self._started.append(service)
            self._log.info("started %s", cls.__name__)
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.stop_all_async()

    async def stop_all_async(self) -> None:
        # Cancellation of the surrounding task must not abandon the remaining
        # services half-stopped: intercept CancelledError per service, finish
        # the teardown, then re-raise it once.
        cancelled = False
        while self._started:
            cancelled |= await self._stop_one_async(self._started.pop())
        if cancelled:
            raise asyncio.CancelledError

    async def _stop_one_async(self, service: ServiceInterface) -> bool:
        """Stop one service; returns True if a cancellation was intercepted."""
        name = type(service).__name__
        try:
            result = service.stop()
            if inspect.isawaitable(result):
                await asyncio.wait_for(asyncio.ensure_future(result), self._stop_grace)
            self._log.info("stopped %s", name)
        except asyncio.CancelledError:
            self._log.warning("cancelled while stopping %s — finishing the remaining teardown", name)
            return True
        except TimeoutError:
            self._log.error("%s.stop() exceeded the %.1fs grace period and was cancelled", name, self._stop_grace)
        except Exception:
            self._log.exception("%s.stop() failed", name)
        return False

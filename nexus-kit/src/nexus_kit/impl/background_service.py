import asyncio
import inspect
import logging
from collections.abc import Coroutine
from typing import Any

from nexus_kit.interfaces.service import ServiceInterface

_log = logging.getLogger("nexus.services")


class BackgroundService(ServiceInterface):
    """An async service whose work runs in background tasks it owns.

    Subclass and write the work, not the lifecycle:

        @singleton
        class CallHistorySync(BackgroundService):
            async def run(self) -> None:            # the main loop, started by start()
                while True:
                    await asyncio.sleep(await self.sync_now())

        @singleton
        class GenerationRunner(BackgroundService):  # no run(): tasks on demand
            def launch(self, settings) -> None:
                self.spawn(self._generate(settings), name="generation")

    Contract:
    - `start()` and `stop()` belong to this class — a subclass defining either
      is rejected when the class is created. Setup and teardown go into the
      optional `on_start()` / `on_stop()` hooks (sync or async).
    - `start()` runs `on_start()`, then launches `run()` if the subclass
      defines it, and returns at once: the service is "up" while its work
      goes on in the background. Starting a started service raises.
    - `spawn(coro)` launches an extra task owned by the service — on demand
      work that `stop()` must not leave behind. Only while the service runs.
    - `stop()` cancels every owned task, waits for them, then runs
      `on_stop()`. Idempotent. A cancellation of the caller itself (e.g.
      ServiceRunner's `stop_grace` running out) is honoured, not swallowed —
      `on_stop()` still runs.
    - A task that dies with an exception is logged with its traceback on the
      "nexus.services" logger; the service and its other tasks keep running.
      A task that simply returns is done — `run()` may be a one-shot.

    The work shares the event loop with everything else (an HTTP server
    included): it must `await`. CPU-heavy or blocking calls go through
    `await asyncio.to_thread(...)` — note that a thread cannot be cancelled,
    so `stop()` returns at once but the process exit waits for it.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for name in ("start", "stop"):
            if name in cls.__dict__:
                raise TypeError(
                    f"{cls.__name__} must not define {name}(): BackgroundService owns start/stop "
                    f"so its tasks are always cancelled correctly — put setup in on_start() and "
                    f"teardown in on_stop(), the work in run() or spawn()"
                )

    # --- the subclass's side ---

    async def run(self) -> None:
        """The main background work. Optional — omit it for spawn()-only services."""

    def on_start(self) -> Any:
        """Setup before run() starts (open a client, load state). Sync or async."""

    def on_stop(self) -> Any:
        """Teardown after every task is stopped. Sync or async; must tolerate a
        partially started service — it also runs after a failed start()."""

    def spawn(self, work: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task:
        """Run `work` as a task this service owns: stop() cancels and awaits it."""
        if not self._state()["running"]:
            work.close()  # never started: close it, or Python warns it was never awaited
            raise RuntimeError(f"{type(self).__name__}.spawn(): the service is not running")
        task = asyncio.create_task(work, name=name or f"{type(self).__name__}.task")
        self._state()["tasks"].add(task)
        task.add_done_callback(self._forget)
        return task

    @property
    def running(self) -> bool:
        return self._state()["running"]

    # --- the lifecycle (final) ---

    async def start(self) -> None:
        state = self._state()
        if state["running"]:
            raise RuntimeError(f"{type(self).__name__} is already started — stop() it first")
        state["running"] = True
        try:
            await _maybe_await(self.on_start())
        except BaseException:
            state["running"] = False  # a failed start leaves a service that can start again
            raise
        if type(self).run is not BackgroundService.run:
            self.spawn(self.run(), name=f"{type(self).__name__}.run")

    async def stop(self) -> None:
        state = self._state()
        state["running"] = False  # spawn() refuses from here on
        tasks = list(state["tasks"])
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                # return_exceptions: a task's own CancelledError or crash is a
                # result here, not a reason to stop waiting for the others. A
                # cancellation of THIS call still raises out of gather.
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await _maybe_await(self.on_stop())

    # --- internals ---

    def _state(self) -> dict[str, Any]:
        # Lazy, not in __init__: subclasses have their own @inject __init__ and
        # must not be able to break the lifecycle by skipping super().__init__().
        state = self.__dict__.get("_background_service_state")
        if state is None:
            state = {"running": False, "tasks": set()}
            self.__dict__["_background_service_state"] = state
        return state

    def _forget(self, task: asyncio.Task) -> None:
        self._state()["tasks"].discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            _log.error(
                "%s: background task %r failed", type(self).__name__, task.get_name(),
                exc_info=(type(error), error, error.__traceback__),
            )


async def _maybe_await(result: Any) -> None:
    if inspect.isawaitable(result):
        await result

import asyncio
import logging
import warnings

import pytest
from injector import inject, singleton

from nexus_kit.impl import BackgroundService, ContainerInjector, ServiceRunner


class Ticker(BackgroundService):
    def __init__(self) -> None:
        self.journal: list[str] = []
        self.ticks = 0

    def on_start(self) -> None:
        self.journal.append("on_start")

    async def run(self) -> None:
        self.journal.append("run")
        try:
            while True:
                self.ticks += 1
                await asyncio.sleep(0.005)
        finally:
            self.journal.append("run cancelled")

    async def on_stop(self) -> None:
        self.journal.append("on_stop")


async def _until(predicate, timeout=1.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.005)


# ---- the lifecycle ------------------------------------------------------------------

def test_start_returns_at_once_and_run_goes_on_in_the_background():
    async def scenario():
        service = Ticker()
        await service.start()
        assert service.running
        await _until(lambda: service.ticks >= 3)
        await service.stop()
        assert not service.running
        assert service.journal == ["on_start", "run", "run cancelled", "on_stop"]
        ticks = service.ticks
        await asyncio.sleep(0.02)
        assert service.ticks == ticks  # really stopped, not merely forgotten

    asyncio.run(scenario())


def test_stop_is_idempotent_and_start_twice_raises():
    async def scenario():
        service = Ticker()
        await service.start()
        with pytest.raises(RuntimeError, match="already started"):
            await service.start()
        await service.stop()
        await service.stop()
        assert service.journal.count("on_stop") == 2  # on_stop must tolerate repeats, like stop()

    asyncio.run(scenario())


def test_a_stopped_service_can_start_again():
    async def scenario():
        service = Ticker()
        await service.start()
        await _until(lambda: "run" in service.journal)
        await service.stop()
        await service.start()
        await _until(lambda: service.journal.count("run") == 2)
        await service.stop()

    asyncio.run(scenario())


def test_a_failed_on_start_leaves_a_service_that_can_start_again():
    class Flaky(BackgroundService):
        def __init__(self) -> None:
            self.attempts = 0

        async def on_start(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("not yet")

        async def run(self) -> None:
            await asyncio.sleep(3600)

    async def scenario():
        service = Flaky()
        with pytest.raises(ConnectionError):
            await service.start()
        assert not service.running
        await service.start()  # not "already started"
        assert service.running
        await service.stop()

    asyncio.run(scenario())


def test_run_is_optional():
    class OnDemand(BackgroundService):
        pass

    async def scenario():
        service = OnDemand()
        await service.start()
        assert service.running
        await service.stop()

    asyncio.run(scenario())


# ---- doing it wrong is not possible -------------------------------------------------

@pytest.mark.parametrize("method", ["start", "stop"])
def test_defining_start_or_stop_is_rejected_at_class_creation(method):
    body = {method: lambda self: None}
    with pytest.raises(TypeError, match=f"must not define {method}"):
        type("Broken", (BackgroundService,), body)


def test_a_subclass_that_skips_super_init_still_works():
    """Apps write their own @inject __init__; forgetting super().__init__() must not
    leave the service without task bookkeeping."""

    @singleton
    class Dependency:
        pass

    @singleton
    class Worker(BackgroundService):
        @inject
        def __init__(self, dependency: Dependency) -> None:
            self.dependency = dependency  # no super().__init__()

        async def run(self) -> None:
            await asyncio.sleep(3600)

    async def scenario():
        worker = ContainerInjector({}).get(Worker)
        await worker.start()
        await worker.stop()
        assert not worker.running

    asyncio.run(scenario())


def test_spawn_outside_the_running_window_raises_and_leaves_no_warning():
    class OnDemand(BackgroundService):
        pass

    async def job():
        await asyncio.sleep(0)

    async def scenario():
        service = OnDemand()
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # "coroutine was never awaited" would fail here
            with pytest.raises(RuntimeError, match="not running"):
                service.spawn(job())
            await service.start()
            await service.stop()
            with pytest.raises(RuntimeError, match="not running"):
                service.spawn(job())

    asyncio.run(scenario())


# ---- spawned work -------------------------------------------------------------------

def test_spawned_tasks_are_cancelled_and_awaited_on_stop():
    class Runner(BackgroundService):
        def __init__(self) -> None:
            self.finished: list[str] = []

        def launch(self, name: str) -> asyncio.Task:
            return self.spawn(self._job(name), name=name)

        async def _job(self, name: str) -> None:
            try:
                await asyncio.sleep(3600)
            finally:
                self.finished.append(name)

    async def scenario():
        service = Runner()
        await service.start()
        first, second = service.launch("a"), service.launch("b")
        await asyncio.sleep(0)
        await service.stop()
        assert first.cancelled() and second.cancelled()
        assert sorted(service.finished) == ["a", "b"]  # awaited: their cleanup ran before stop() returned

    asyncio.run(scenario())


def test_a_crashing_task_is_logged_and_the_rest_keep_running(caplog):
    class Mixed(BackgroundService):
        def __init__(self) -> None:
            self.ticks = 0

        async def run(self) -> None:
            while True:
                self.ticks += 1
                await asyncio.sleep(0.005)

        def fail(self) -> asyncio.Task:
            return self.spawn(self._boom(), name="boom")

        async def _boom(self) -> None:
            raise ValueError("kaboom")

    async def scenario():
        service = Mixed()
        await service.start()
        task = service.fail()
        await asyncio.wait([task])
        ticks = service.ticks
        await _until(lambda: service.ticks > ticks)  # the main loop survived
        await service.stop()

    with caplog.at_level(logging.ERROR, logger="nexus.services"):
        asyncio.run(scenario())

    [record] = [r for r in caplog.records if "boom" in r.getMessage()]
    assert "Mixed" in record.getMessage()
    assert record.exc_info and record.exc_info[0] is ValueError  # the traceback is there


def test_a_one_shot_run_that_returns_is_not_an_error(caplog):
    class OneShot(BackgroundService):
        async def run(self) -> None:
            return None

    async def scenario():
        service = OneShot()
        await service.start()
        await asyncio.sleep(0.01)
        assert service.running  # the service stays up; only its task is done
        await service.stop()

    with caplog.at_level(logging.ERROR, logger="nexus.services"):
        asyncio.run(scenario())
    assert not caplog.records


# ---- cancellation of stop() itself --------------------------------------------------

class Stubborn(BackgroundService):
    """A task that shrugs off one cancellation and keeps working — the case a
    bounded stop exists for."""

    def __init__(self) -> None:
        self.on_stop_ran = False

    async def run(self) -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await asyncio.sleep(3600)  # ignores the first cancel

    def on_stop(self) -> None:
        self.on_stop_ran = True


def test_a_cancelled_stop_is_honoured_and_still_runs_on_stop():
    async def scenario():
        service = Stubborn()
        await service.start()
        await asyncio.sleep(0)
        stopping = asyncio.create_task(service.stop())
        await asyncio.sleep(0.02)
        assert not stopping.done()  # waiting for the stubborn task
        stopping.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stopping  # the caller's cancellation propagates, it is not swallowed
        assert service.on_stop_ran

    asyncio.run(scenario())


def test_under_service_runner_a_stubborn_service_cannot_hang_the_teardown(caplog):
    journal: list[str] = []

    @singleton
    class Before(BackgroundService):
        def on_stop(self) -> None:
            journal.append("Before stopped")

    @singleton
    class Hung(Stubborn):
        pass

    async def scenario():
        container = ContainerInjector({})
        async with ServiceRunner(container, [Before, Hung], stop_grace=0.05):
            await asyncio.sleep(0.01)
        return container.get(Hung)

    with caplog.at_level(logging.ERROR, logger="nexus.services"):
        hung = asyncio.run(scenario())

    assert hung.on_stop_ran
    assert journal == ["Before stopped"]  # the runner moved on to the next service
    assert any("grace period" in r.getMessage() for r in caplog.records)


def test_sync_runner_context_rejects_a_background_service():
    @singleton
    class Worker(BackgroundService):
        pass

    with pytest.raises(TypeError, match="async"):
        with ServiceRunner(ContainerInjector({}), [Worker]):
            pass

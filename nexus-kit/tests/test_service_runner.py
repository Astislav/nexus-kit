import asyncio

import pytest
from injector import inject, singleton

from nexus_kit.impl import ContainerInjector, ServiceRunner
from nexus_kit.interfaces import ServiceInterface


class FakeContainer:
    """Hands out pre-built instances; unknown types raise, like a DI error would."""

    def __init__(self, *instances):
        self._instances = {type(i): i for i in instances}

    def get(self, cls):
        return self._instances[cls]


def sync_service(name, journal, fail_start=False):
    class Service(ServiceInterface):
        def start(self):
            if fail_start:
                raise RuntimeError(f"{name} failed to start")
            journal.append(f"+{name}")

        def stop(self):
            journal.append(f"-{name}")

    Service.__name__ = name
    return Service()


def async_service(name, journal, stop_delay=0.0):
    class Service(ServiceInterface):
        async def start(self):
            journal.append(f"+{name}")

        async def stop(self):
            await asyncio.sleep(stop_delay)
            journal.append(f"-{name}")

    Service.__name__ = name
    return Service()


def make_runner(*services, **kwargs):
    return ServiceRunner(FakeContainer(*services), [type(s) for s in services], **kwargs)


def test_sync_starts_in_order_stops_in_reverse():
    journal = []
    runner = make_runner(sync_service("A", journal), sync_service("B", journal))
    with runner:
        journal.append("run")
    assert journal == ["+A", "+B", "run", "-B", "-A"]


def test_sync_failed_start_rolls_back_started_and_reraises():
    journal = []
    runner = make_runner(sync_service("A", journal), sync_service("B", journal, fail_start=True))
    with pytest.raises(RuntimeError, match="B failed"):
        with runner:
            journal.append("run")
    # the failed service gets a best-effort stop() too, then the rollback
    assert journal == ["+A", "-B", "-A"]


def test_sync_failed_start_still_stops_the_failed_service():
    """Regression: start() that opened a resource and then raised leaked it."""

    class HalfOpen(ServiceInterface):
        def __init__(self, journal):
            self._journal = journal

        def start(self):
            self._journal.append("+half:opened")  # resource acquired...
            raise RuntimeError("...then start failed")

        def stop(self):
            self._journal.append("-half:closed")

    journal = []
    a = sync_service("A", journal)
    half = HalfOpen(journal)
    runner = ServiceRunner(FakeContainer(a, half), [type(a), type(half)])
    with pytest.raises(RuntimeError):
        with runner:
            pass
    assert journal == ["+A", "+half:opened", "-half:closed", "-A"]


def test_sync_body_exception_still_stops_services():
    journal = []
    runner = make_runner(sync_service("A", journal))
    with pytest.raises(ValueError):
        with runner:
            raise ValueError("app crashed")
    assert journal == ["+A", "-A"]


def test_sync_context_rejects_async_service_and_rolls_back():
    journal = []
    runner = make_runner(sync_service("A", journal), async_service("X", journal))
    with pytest.raises(TypeError, match="async"):
        with runner:
            pass
    assert journal == ["+A", "-A"]


def test_di_resolution_failure_rolls_back_started():
    """Regression: container.get() raising used to leave started services running."""

    class Unregistered(ServiceInterface):
        def start(self): ...
        def stop(self): ...

    journal = []
    a = sync_service("A", journal)
    runner = ServiceRunner(FakeContainer(a), [type(a), Unregistered])
    with pytest.raises(KeyError):
        with runner:
            pass
    assert journal == ["+A", "-A"]


def test_async_order_with_mixed_sync_service():
    journal = []
    runner = make_runner(async_service("X", journal), sync_service("S", journal), async_service("Z", journal))

    async def scenario():
        async with runner:
            journal.append("run")

    asyncio.run(scenario())
    assert journal == ["+X", "+S", "run", "+Z", "-Z", "-S", "-X"] or journal == ["+X", "+S", "+Z", "run", "-Z", "-S", "-X"]


def test_async_failed_start_rolls_back():
    journal = []
    runner = make_runner(async_service("X", journal), sync_service("BAD", journal, fail_start=True))

    async def scenario():
        async with runner:
            pass

    with pytest.raises(RuntimeError, match="BAD"):
        asyncio.run(scenario())
    # the failed service gets a best-effort stop() too, then the rollback
    assert journal == ["+X", "-BAD", "-X"]


def test_async_failed_start_still_stops_the_failed_service():
    """Regression: async start() that opened a resource and then raised leaked it."""

    class HalfOpen(ServiceInterface):
        def __init__(self, journal):
            self._journal = journal

        async def start(self):
            self._journal.append("+half:opened")
            raise RuntimeError("...then start failed")

        async def stop(self):
            self._journal.append("-half:closed")

    journal = []
    x = async_service("X", journal)
    half = HalfOpen(journal)
    runner = ServiceRunner(FakeContainer(x, half), [type(x), type(half)])

    async def scenario():
        async with runner:
            pass

    with pytest.raises(RuntimeError):
        asyncio.run(scenario())
    assert journal == ["+X", "+half:opened", "-half:closed", "-X"]


def test_async_stop_grace_cancels_laggard_but_stops_the_rest():
    journal = []
    fast, slow = async_service("FAST", journal), async_service("SLOW", journal, stop_delay=5.0)
    runner = make_runner(fast, slow, stop_grace=0.1)

    async def scenario():
        async with runner:
            pass

    asyncio.run(scenario())
    assert journal == ["+FAST", "+SLOW", "-FAST"]  # SLOW cancelled, FAST still stopped


def test_cancellation_during_teardown_finishes_remaining_stops():
    """Regression: CancelledError used to abandon the rest of the teardown."""
    journal = []
    a = sync_service("A", journal)
    b = async_service("B", journal, stop_delay=1.0)
    runner = make_runner(a, b, stop_grace=5.0)

    async def scenario():
        async def run():
            async with runner:
                journal.append("run")
                await asyncio.sleep(10)

        task = asyncio.create_task(run())
        await asyncio.sleep(0.05)
        task.cancel()          # cancels the body -> teardown begins with B.stop()
        await asyncio.sleep(0.1)
        task.cancel()          # lands inside B's in-flight stop
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert "-A" in journal  # sync service still stopped after the cancellation


def test_integration_with_container_injector():
    journal = []

    @singleton
    class Dependency:
        pass

    @singleton
    class Managed(ServiceInterface):
        @inject
        def __init__(self, dep: Dependency) -> None:
            self._dep = dep

        def start(self):
            journal.append("+managed")

        def stop(self):
            journal.append("-managed")

    container = ContainerInjector({})
    with ServiceRunner(container, [Managed]):
        assert container.get(Managed) is container.get(Managed)
    assert journal == ["+managed", "-managed"]

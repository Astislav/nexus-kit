import asyncio
import socket

import httpx
import pytest
from fastapi import FastAPI
from injector import singleton

from nexus_kit.impl import ContainerInjector, ServiceRunner
from nexus_kit_fastapi import HttpService, Injected


@singleton
class Greeter:
    def greet(self) -> str:
        return "hello from the container"


@singleton
class PingService(HttpService):
    port = 0  # ephemeral — parallel-safe tests
    log_level = "warning"

    def create_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/ping")
        def ping(greeter: Greeter = Injected(Greeter)):
            return {"pong": greeter.greet()}

        return app


def test_full_lifecycle_serves_and_stops_cleanly():
    async def scenario():
        container = ContainerInjector({})
        service = container.get(PingService)

        await service.start()
        try:
            url = f"http://127.0.0.1:{service.bound_port}/ping"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            assert response.status_code == 200
            assert response.json() == {"pong": "hello from the container"}
        finally:
            await service.stop()
            await service.stop()  # idempotent

    asyncio.run(scenario())


def test_runs_under_service_runner():
    async def scenario():
        container = ContainerInjector({})
        async with ServiceRunner(container, [PingService]):
            service = container.get(PingService)
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{service.bound_port}/ping")
            assert response.status_code == 200
        # leaving the block stopped uvicorn; the port is released
        with pytest.raises(RuntimeError):
            _ = service.bound_port

    asyncio.run(scenario())


def test_start_raises_on_busy_port_instead_of_failing_silently():
    async def scenario():
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        busy_port = blocker.getsockname()[1]
        try:

            @singleton
            class Collider(HttpService):
                port = busy_port
                log_level = "critical"

                def create_app(self) -> FastAPI:
                    return FastAPI()

            container = ContainerInjector({})
            service = container.get(Collider)
            with pytest.raises(OSError):  # we bind the socket ourselves — a plain, catchable error
                await service.start()
        finally:
            blocker.close()

    asyncio.run(scenario())

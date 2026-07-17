from fastapi import FastAPI
from fastapi.testclient import TestClient
from injector import singleton

from nexus_kit.impl import ContainerInjector
from nexus_kit_fastapi import Injected, attach_container


@singleton
class Counter:
    def __init__(self) -> None:
        self.value = 0

    def bump(self) -> int:
        self.value += 1
        return self.value


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/bump")
    def bump(counter: Counter = Injected(Counter)):
        return {"value": counter.bump()}

    return app


def test_injected_resolves_the_same_singleton_across_requests():
    app = build_app()
    attach_container(app, ContainerInjector({}))
    client = TestClient(app)

    assert client.get("/bump").json() == {"value": 1}
    assert client.get("/bump").json() == {"value": 2}  # same instance — container singleton


def test_missing_container_gives_503_not_a_crash():
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/bump")
    assert response.status_code == 503
    assert "container" in response.json()["detail"]


def test_container_set_overrides_for_tests():
    """The nexus-native test override: bind a fake into the container."""

    class FakeCounter(Counter):
        def bump(self) -> int:
            return 42

    app = build_app()
    container = ContainerInjector({})
    container.set(Counter, FakeCounter())
    attach_container(app, container)

    assert TestClient(app).get("/bump").json() == {"value": 42}

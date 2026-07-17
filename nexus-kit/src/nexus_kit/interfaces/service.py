from abc import ABC, abstractmethod


class ServiceInterface(ABC):
    """Contract for a long-lived service managed by ServiceRunner.

    Both methods may be sync or async — the runner awaits the result when it
    is awaitable. In a sync runner context (`with runner:`) async services
    are rejected.

    stop() must be idempotent: the runner may call it after a failed start()
    or more than once during teardown.
    """

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

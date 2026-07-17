from __future__ import annotations

from abc import ABC, abstractmethod

from nexus_kit.interfaces.container import ContainerInterface
from nexus_kit.interfaces.environment import EnvironmentInterface


class ApplicationInterface(ABC):
    @abstractmethod
    def __init__(
            self, environment: EnvironmentInterface, container: ContainerInterface
    ): ...

    @abstractmethod
    def run(self): ...

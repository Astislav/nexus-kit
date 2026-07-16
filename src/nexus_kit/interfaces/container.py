from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar


T = TypeVar("T")


class ContainerInterface(ABC):
    @abstractmethod
    def get(self, cls: Type[T]) -> T: ...

    @abstractmethod
    def set(self, cls: Type[Any], value: Any) -> "ContainerInterface": ...

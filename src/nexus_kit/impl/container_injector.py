from typing import Any, Mapping, Type, TypeVar

from injector import Injector, singleton

from nexus_kit.interfaces.container import ContainerInterface


@singleton
class ContainerInjector(ContainerInterface):
    T = TypeVar("T")

    def __init__(self, bindings: Mapping[Type[Any], Any]):
        self.__injector = Injector()
        self.__injector.binder.bind(Injector, to=self.__injector)
        self.__injector.binder.bind(ContainerInterface, to=self)

        for cls, value in bindings.items():
            self.set(cls, value)

    def get(self, cls: Type[T]) -> T:
        return self.__injector.get(cls)

    def set(self, cls: Type[T], value: Any) -> "ContainerInterface":
        self.__injector.binder.bind(cls, to=value)
        return self

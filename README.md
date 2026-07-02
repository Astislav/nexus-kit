# nexus

Minimal Python application framework. Single entry point, typed config, dependency injection.

## Install

```bash
# uv
uv add "nexus[full] @ git+https://github.com/Astislav/nexus"

# pip
pip install "nexus[full] @ git+https://github.com/Astislav/nexus"
```

## Bootstrap a new app

```bash
nexus new my-app
cd my-app

# install dependencies:
uv sync          # uv
pip install -e . # pip

python main.py
# → Running my-app
```

## What you get

```
my-app/
├── main.py                    # entry point
├── pyproject.toml
├── .env
└── app/
    ├── application.py         # extend ApplicationInterface
    └── config/
        ├── di.py              # DI_CONFIG = {Interface: Implementation}
        └── environment.py     # extend EnvironmentInterface
```

## Add a service

**1. Define an interface:**

```python
# app/services/greeter_interface.py
from abc import ABC, abstractmethod

class GreeterInterface(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...
```

**2. Implement it:**

```python
# app/services/greeter.py
from injector import inject, singleton
from app.services.greeter_interface import GreeterInterface

@singleton
class Greeter(GreeterInterface):
    @inject
    def __init__(self) -> None: ...

    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

**3. Register in DI:**

```python
# app/config/di.py
from app.services.greeter import Greeter
from app.services.greeter_interface import GreeterInterface

DI_CONFIG = {
    GreeterInterface: Greeter,
}
```

**4. Use in Application:**

```python
# app/application.py
from nexus.interfaces import ApplicationInterface, ContainerInterface, EnvironmentInterface
from app.services.greeter_interface import GreeterInterface

class Application(ApplicationInterface):
    def __init__(self, environment: EnvironmentInterface, container: ContainerInterface) -> None:
        self._greeter = container.get(GreeterInterface)

    def run(self) -> None:
        print(self._greeter.greet("world"))
```

## What nexus provides

| Symbol | Import | Description |
|--------|--------|-------------|
| `ApplicationInterface` | `nexus.interfaces` | Bootstrap contract: `__init__(env, container)` + `run()` |
| `ContainerInterface` | `nexus.interfaces` | DI contract: `get(cls)` + `set(cls, value)` |
| `EnvironmentInterface` | `nexus.interfaces` | Typed config base (Pydantic BaseSettings) |
| `Root` | `nexus` | Path util for dev and PyInstaller-bundled environments |
| `ContainerInjector` | `nexus.impl` | `ContainerInterface` impl via [injector](https://injector.readthedocs.io/) |

## What nexus does NOT provide

Domain logic, UI, data access — those belong in your app.

## Optional extras

| Extra | What it unlocks |
|-------|-----------------|
| `nexus[injector]` | `ContainerInjector` |
| `nexus[pydantic]` | `EnvironmentInterface` |
| `nexus[full]` | Both — recommended |

## License

MIT © Astislav Bozhevolnov

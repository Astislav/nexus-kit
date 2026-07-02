import sys
from pathlib import Path


_TEMPLATES: dict[str, str] = {
    "main.py": """\
import faulthandler

from app.application import Application
from app.config.di import DI_CONFIG
from app.config.environment import Environment
from nexus import Root
from nexus.impl import ContainerInjector

if __name__ == "__main__":
    faulthandler.enable(all_threads=True)

    env = Environment(Root.external(".env"))
    container = ContainerInjector(DI_CONFIG)
    container.set(Environment, env)
    Application(env, container).run()
""",
    "pyproject.toml": """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{APP_NAME}}"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "nexus[full] @ git+https://github.com/Astislav/nexus",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]
""",
    ".env": """\
APP_NAME={{APP_NAME}}
DEBUG=false
""",
    "app/__init__.py": "",
    "app/application.py": """\
from nexus.interfaces import ApplicationInterface, ContainerInterface

from app.config.environment import Environment
from app.services.greeter_interface import GreeterInterface


class Application(ApplicationInterface):
    def __init__(self, environment: Environment, container: ContainerInterface) -> None:
        self._env = environment
        self._greeter = container.get(GreeterInterface)

    def run(self) -> None:
        print(f"[{self._env.APP_NAME}] debug={self._env.DEBUG}")
        print(self._greeter.greet("world"))
""",
    "app/config/__init__.py": "",
    "app/config/di.py": """\
# Register your services here: {Interface: Implementation}
from app.services.greeter import Greeter
from app.services.greeter_interface import GreeterInterface

DI_CONFIG = {
    GreeterInterface: Greeter,
}
""",
    "app/config/environment.py": """\
from pathlib import Path

from injector import singleton

from nexus.interfaces import EnvironmentInterface


@singleton
class Environment(EnvironmentInterface):
    # Add your config fields here — they are read from .env automatically
    APP_NAME: str = "{{APP_NAME}}"
    DEBUG: bool = False

    def __init__(self, env_path: Path) -> None:
        super().__init__(_env_file=env_path)
""",
    "app/services/__init__.py": "",
    "app/services/greeter_interface.py": """\
from abc import ABC, abstractmethod


class GreeterInterface(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...
""",
    "app/services/greeter.py": """\
from injector import singleton

from app.services.greeter_interface import GreeterInterface


@singleton
class Greeter(GreeterInterface):
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
""",
}


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "new":
        print("Usage: nexus new <app-name>")
        sys.exit(1)

    app_name = sys.argv[2]
    root = Path(app_name)

    if root.exists():
        print(f"Error: '{app_name}' already exists")
        sys.exit(1)

    root.mkdir()

    for rel_path, content in _TEMPLATES.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.replace("{{APP_NAME}}", app_name), encoding="utf-8")

    print(f"Created {app_name}/")
    print(f"")
    print(f"  cd {app_name}")
    print(f"")
    print(f"  # install dependencies:")
    print(f"  uv sync                  # uv")
    print(f"  pip install -e .         # pip")
    print(f"")
    print(f"  python main.py")

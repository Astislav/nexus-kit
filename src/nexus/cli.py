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
    ".env": "APP_NAME={{APP_NAME}}\n",
    "app/__init__.py": "",
    "app/application.py": """\
from nexus.interfaces import ApplicationInterface, ContainerInterface, EnvironmentInterface


class Application(ApplicationInterface):
    def __init__(self, environment: EnvironmentInterface, container: ContainerInterface) -> None:
        self._env = environment
        self._container = container

    def run(self) -> None:
        print(f"Running {self._env.APP_NAME}")
""",
    "app/config/__init__.py": "",
    "app/config/di.py": "DI_CONFIG = {}\n",
    "app/config/environment.py": """\
from pathlib import Path

from injector import singleton

from nexus.interfaces import EnvironmentInterface


@singleton
class Environment(EnvironmentInterface):
    APP_NAME: str = "{{APP_NAME}}"

    def __init__(self, env_path: Path) -> None:
        super().__init__(_env_file=env_path)
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

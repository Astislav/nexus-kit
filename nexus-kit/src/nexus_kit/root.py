import sys
import sysconfig
from pathlib import Path


class Root:
    @staticmethod
    def internal(*relative_parts: str) -> str:
        if hasattr(sys, "_MEIPASS"):
            base_dir = Path(sys._MEIPASS)
        else:
            base_dir = Root._dev_base()
        return str(base_dir.joinpath(*relative_parts))

    @staticmethod
    def external(*relative_parts: str) -> str:
        if hasattr(sys, "_MEIPASS"):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Root._dev_base()
        return str(base_dir.joinpath(*relative_parts))

    @staticmethod
    def _dev_base() -> Path:
        # Anchor to the entry script's directory, not cwd: launching
        # `python d:/apps/game/main.py` from another directory (IDE, task
        # scheduler, shortcut) must still find .env next to main.py —
        # matching the frozen build, which anchors to the exe.
        main_file = getattr(sys.modules.get("__main__"), "__file__", None)
        if main_file:
            entry = Path(main_file).resolve()
            if not Root._is_installed_entry(entry):
                return entry.parent
        # No entry script of the app's own: REPL, `python -c`, or a runner
        # installed into the environment (pytest, a console script). Its
        # directory is somewhere inside .venv, never the app — anchor to the
        # project the process works in instead.
        return Root._project_dir(Path.cwd())

    @staticmethod
    def _is_installed_entry(entry: Path) -> bool:
        """Entry script that belongs to the Python environment, not to an app.

        `python -m pytest` runs site-packages/pytest/__main__.py; `pytest` and any
        other console script run from the environment's scripts directory. An
        app's own main.py lives in neither.
        """
        if {"site-packages", "dist-packages"} & {part.lower() for part in entry.parts}:
            return True
        scripts = sysconfig.get_path("scripts")
        return bool(scripts) and entry.is_relative_to(Path(scripts).resolve())

    @staticmethod
    def _project_dir(start: Path) -> Path:
        """Nearest directory at or above `start` holding a pyproject.toml, else `start`.

        Test runners are usually started from the project root, but IDEs and
        `cd tests && pytest` start them deeper — the project is still the same.
        """
        for directory in (start, *start.parents):
            if (directory / "pyproject.toml").is_file():
                return directory
        return start

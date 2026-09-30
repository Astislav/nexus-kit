import sys
import sysconfig
from pathlib import Path


class Root:
    # The fallback anchor, resolved once per process: the project does not move
    # while the process runs, even if a test changes the working directory.
    _project_base: Path | None = None

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
        if main_file and not Root._under_test_runner():
            entry = Path(main_file).resolve()
            if not Root._is_tool_entry(entry):
                return entry.parent
        # The entry script is not the app's own: a test run, a tool, REPL,
        # `python -c`. Anchor to the project the process was started in.
        if Root._project_base is None:
            Root._project_base = Root._project_dir(Path.cwd())
        return Root._project_base

    @staticmethod
    def _under_test_runner() -> bool:
        """pytest is driving this process — whoever launched it.

        Asked of the loaded modules, not of the entry script's location: `pytest`,
        `python -m pytest`, PyCharm's and VS Code's own runner scripts (which live
        in the IDE's directory, outside any environment) all import pytest before
        the first test module loads. An app never does.
        """
        return "pytest" in sys.modules or "_pytest" in sys.modules

    @staticmethod
    def _is_tool_entry(entry: Path) -> bool:
        """Entry script that belongs to Python or its environment, not to an app.

        A console script runs from the environment's scripts directory, `python -m
        <installed tool>` from site-packages, `python -m unittest` (or pdb, timeit)
        from the standard library. An app's own main.py lives in none of them.
        """
        if {"site-packages", "dist-packages"} & {part.lower() for part in entry.parts}:
            return True
        for name in ("scripts", "stdlib", "platstdlib"):
            location = sysconfig.get_path(name)
            if location and entry.is_relative_to(Path(location).resolve()):
                return True
        return False

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

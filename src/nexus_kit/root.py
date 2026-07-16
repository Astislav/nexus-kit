import sys
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
            return Path(main_file).resolve().parent
        return Path.cwd()  # REPL, python -c

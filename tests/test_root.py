import sys
import types
from pathlib import Path

from nexus_kit import Root


def test_dev_paths_anchor_to_entry_script_dir(monkeypatch, tmp_path):
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(tmp_path / "main.py")
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert Root.external("data", "app.db") == str(tmp_path / "data" / "app.db")
    assert Root.internal("assets") == str(tmp_path / "assets")


def test_dev_fallback_to_cwd_without_entry_script(monkeypatch, tmp_path):
    fake_main = types.ModuleType("__main__")  # REPL / python -c: no __file__
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)

    assert Root.external(".env") == str(tmp_path / ".env")


def test_frozen_paths_anchor_to_bundle_and_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "app.exe"))

    assert Root.internal("templates", "report.html") == str(tmp_path / "bundle" / "templates" / "report.html")
    assert Root.external(".env") == str((tmp_path / "dist").resolve() / ".env")

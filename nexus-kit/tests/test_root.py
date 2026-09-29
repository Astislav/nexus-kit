import sys
import types
from pathlib import Path

import pytest

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


def _entry(monkeypatch, path):
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(path)
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)


def _project(tmp_path):
    project = tmp_path / "app"
    (project / "tests").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = 'app'\n", encoding="utf-8")
    return project


def test_runner_from_site_packages_anchors_to_the_project(monkeypatch, tmp_path):
    """`python -m pytest`: __main__ is site-packages/pytest/__main__.py. Anchoring to
    its directory sent every Root path into the venv; the project is what the tests
    run against — found from cwd, even when started from a subdirectory."""
    project = _project(tmp_path)
    _entry(monkeypatch, project / ".venv" / "Lib" / "site-packages" / "pytest" / "__main__.py")
    monkeypatch.chdir(project / "tests")

    assert Root.external(".env") == str(project / ".env")
    assert Root.internal("templates") == str(project / "templates")


def test_console_script_in_the_environment_anchors_to_the_project(monkeypatch, tmp_path):
    """`pytest` / any console script: __main__ lives in the environment's scripts dir
    (on Windows inside the .exe launcher itself)."""
    project = _project(tmp_path)
    scripts = project / ".venv" / "Scripts"
    monkeypatch.setattr("sysconfig.get_path", lambda name: str(scripts) if name == "scripts" else "")
    _entry(monkeypatch, scripts / "pytest.exe" / "__main__.py")
    monkeypatch.chdir(project)

    assert Root.external(".env") == str(project / ".env")


def test_installed_runner_outside_any_project_falls_back_to_cwd(monkeypatch, tmp_path):
    if any((d / "pyproject.toml").is_file() for d in tmp_path.parents):
        pytest.skip("a pyproject.toml above the temp dir makes 'no project' unreachable here")
    _entry(monkeypatch, tmp_path / "venv" / "lib" / "python3.14" / "site-packages" / "tool" / "__main__.py")
    monkeypatch.chdir(tmp_path)

    assert Root.external(".env") == str(tmp_path / ".env")


def test_an_app_entry_script_still_wins_over_pyproject(monkeypatch, tmp_path):
    """Nested entry script (apps/game/main.py) keeps anchoring next to itself —
    the pyproject fallback is only for entries that are not the app's."""
    project = _project(tmp_path)
    game = project / "apps" / "game"
    game.mkdir(parents=True)
    _entry(monkeypatch, game / "main.py")
    monkeypatch.chdir(project)

    assert Root.external(".env") == str(game / ".env")


def test_under_this_very_pytest_root_is_not_inside_the_environment():
    """The real process: whatever launched these tests, Root must not point into the venv."""
    base = Path(Root.external()).resolve()

    assert not base.is_relative_to(Path(sys.prefix).resolve())
    assert (base / "pyproject.toml").is_file()

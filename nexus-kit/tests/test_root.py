import subprocess
import sys
import textwrap
import types
from pathlib import Path

import pytest

from nexus_kit import Root


@pytest.fixture(autouse=True)
def fresh_anchor(monkeypatch):
    """Root resolves the project anchor once per process; each test gets its own."""
    monkeypatch.setattr(Root, "_project_base", None)


@pytest.fixture
def as_plain_python(monkeypatch):
    """These tests run under pytest themselves; this is the process seen by an app
    started with plain `python ...`, where no test runner is loaded."""
    monkeypatch.setattr(Root, "_under_test_runner", staticmethod(lambda: False))


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


# ---- python main.py ---------------------------------------------------------------------

def test_dev_paths_anchor_to_entry_script_dir(monkeypatch, tmp_path, as_plain_python):
    _entry(monkeypatch, tmp_path / "main.py")

    assert Root.external("data", "app.db") == str(tmp_path / "data" / "app.db")
    assert Root.internal("assets") == str(tmp_path / "assets")


def test_an_app_entry_script_wins_over_pyproject(monkeypatch, tmp_path, as_plain_python):
    """Nested entry script (apps/game/main.py) keeps anchoring next to itself —
    the pyproject fallback is only for entries that are not the app's."""
    project = _project(tmp_path)
    game = project / "apps" / "game"
    game.mkdir(parents=True)
    _entry(monkeypatch, game / "main.py")
    monkeypatch.chdir(project)

    assert Root.external(".env") == str(game / ".env")


def test_dev_fallback_to_cwd_without_entry_script(monkeypatch, tmp_path, as_plain_python):
    if any((d / "pyproject.toml").is_file() for d in tmp_path.parents):
        pytest.skip("a pyproject.toml above the temp dir makes 'no project' unreachable here")
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


# ---- the entry script is a tool, not the app ---------------------------------------------

def test_runner_from_site_packages_anchors_to_the_project(monkeypatch, tmp_path, as_plain_python):
    """`python -m <installed tool>`: __main__ is in site-packages. The project is found
    from cwd, even when started from a subdirectory."""
    project = _project(tmp_path)
    _entry(monkeypatch, project / ".venv" / "Lib" / "site-packages" / "tool" / "__main__.py")
    monkeypatch.chdir(project / "tests")

    assert Root.external(".env") == str(project / ".env")
    assert Root.internal("templates") == str(project / "templates")


def test_console_script_in_the_environment_anchors_to_the_project(monkeypatch, tmp_path, as_plain_python):
    """A console script: __main__ lives in the environment's scripts dir (on Windows
    inside the .exe launcher itself)."""
    project = _project(tmp_path)
    scripts = project / ".venv" / "Scripts"
    monkeypatch.setattr("sysconfig.get_path", lambda name: str(scripts) if name == "scripts" else "")
    _entry(monkeypatch, scripts / "tool.exe" / "__main__.py")
    monkeypatch.chdir(project)

    assert Root.external(".env") == str(project / ".env")


def test_a_standard_library_entry_anchors_to_the_project(monkeypatch, tmp_path, as_plain_python):
    """`python -m unittest` (pdb, timeit): __main__ is in the standard library."""
    project = _project(tmp_path)
    stdlib = tmp_path / "python" / "Lib"
    monkeypatch.setattr("sysconfig.get_path", lambda name: str(stdlib) if name == "stdlib" else "")
    _entry(monkeypatch, stdlib / "unittest" / "__main__.py")
    monkeypatch.chdir(project)

    assert Root.external(".env") == str(project / ".env")


# ---- under pytest, whoever launched it ---------------------------------------------------

def test_under_pytest_an_entry_script_outside_any_environment_is_still_not_the_app(monkeypatch, tmp_path):
    """IDE runners (PyCharm's _jb_pytest_runner.py, VS Code's adapter) live in the IDE's
    own directory — not in .venv, not in the standard library. Where the runner sits says
    nothing; that pytest is loaded says everything."""
    project = _project(tmp_path)
    ide = tmp_path / "ide" / "helpers"
    ide.mkdir(parents=True)
    _entry(monkeypatch, ide / "_jb_pytest_runner.py")
    monkeypatch.chdir(project / "tests")

    assert Root.external(".env") == str(project / ".env")


def test_the_anchor_does_not_follow_a_later_chdir(monkeypatch, tmp_path):
    """Tests chdir into temp dirs all the time; the project they belong to stays put."""
    project = _project(tmp_path)
    _entry(monkeypatch, tmp_path / "ide" / "_jb_pytest_runner.py")
    monkeypatch.chdir(project)
    assert Root.external(".env") == str(project / ".env")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert Root.external(".env") == str(project / ".env")


def test_under_this_very_pytest_root_is_the_project(monkeypatch):
    """The real process, no fakes: whatever launched these tests."""
    base = Path(Root.external()).resolve()

    assert (base / "pyproject.toml").is_file()
    assert not base.is_relative_to(Path(sys.prefix).resolve())


# ---- real processes ----------------------------------------------------------------------

def _run(args, cwd):
    result = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    [line] = [line for line in (result.stdout + result.stderr).splitlines() if line.startswith("ROOT=")]
    return Path(line.removeprefix("ROOT="))


def test_a_real_ide_style_runner_outside_the_environment(tmp_path):
    """End to end, the way PyCharm does it: a runner script in a foreign directory
    imports pytest and runs the project's tests, started from the tests directory."""
    project = _project(tmp_path)
    (project / "tests" / "test_where.py").write_text(textwrap.dedent("""
        from nexus_kit import Root

        def test_where():
            print("ROOT=" + Root.external())
    """), encoding="utf-8")
    runner = tmp_path / "ide" / "helpers" / "_ide_pytest_runner.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("import sys, pytest\nsys.exit(pytest.main(sys.argv[1:]))\n", encoding="utf-8")

    base = _run([str(runner), "-q", "-s", "-p", "no:cacheprovider", "test_where.py"], cwd=project / "tests")

    assert base == project


def test_a_real_unittest_run(tmp_path):
    project = _project(tmp_path)
    (project / "tests" / "test_where.py").write_text(textwrap.dedent("""
        import unittest
        from nexus_kit import Root

        class Where(unittest.TestCase):
            def test_where(self):
                print("ROOT=" + Root.external())
    """), encoding="utf-8")

    base = _run(["-m", "unittest", "tests/test_where.py"], cwd=project)

    assert base == project


def test_a_real_app_entry_script_launched_from_elsewhere(tmp_path):
    """The original promise, unchanged: `python d:/apps/game/main.py` from any cwd
    anchors next to main.py."""
    app = tmp_path / "game"
    app.mkdir()
    (app / "main.py").write_text("from nexus_kit import Root\nprint('ROOT=' + Root.external())\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    assert _run([str(app / "main.py")], cwd=elsewhere) == app

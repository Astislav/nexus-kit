import os
import re
import subprocess
import sys

import pytest

from nexus_kit import cli


def scaffold(tmp_path, monkeypatch, name="probe"):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["nexus", "new", name])
    cli.main()
    return tmp_path / name


def test_scaffold_files_placeholders_and_pin(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch)

    for rel_path in cli._TEMPLATES:
        assert (proj / rel_path).exists(), rel_path

    for rel_path in cli._TEMPLATES:
        content = (proj / rel_path).read_text(encoding="utf-8")
        assert "{{" not in content, f"unreplaced placeholder in {rel_path}"

    pyproject = (proj / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"nexus-kit~=\d+\.\d+\.\d+", pyproject)  # PyPI dist, pinned to the CLI's own version

    gitignore = (proj / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore and ".venv/" in gitignore


def test_refuses_to_overwrite_existing_directory(tmp_path, monkeypatch):
    scaffold(tmp_path, monkeypatch, "dup")
    with pytest.raises(SystemExit):
        scaffold(tmp_path, monkeypatch, "dup")


def freeze(proj, monkeypatch, *extra):
    monkeypatch.chdir(proj)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "freeze", *extra])
    cli.main()


def test_freeze_generates_packaging_artifacts(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "frost")
    freeze(proj, monkeypatch)

    spec = (proj / "app.spec").read_text(encoding="utf-8")
    assert 'name="frost"' in spec  # exe name defaults to the directory name
    assert "{{" not in spec
    assert "BUNDLED" in spec and "runtime_tmpdir=None" in spec

    bat = (proj / "build.bat").read_text(encoding="utf-8")
    sh_bytes = (proj / "build.sh").read_bytes()
    assert "pyinstaller app.spec" in bat
    assert b"\r" not in sh_bytes  # POSIX script must be LF-only even when generated on Windows

    gitignore = (proj / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "dist/" in gitignore and "build/" in gitignore
    assert "*.spec" not in gitignore  # app.spec is source


def test_freeze_removes_legacy_spec_ignore_and_keeps_existing_lines(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "legacy")
    (proj / ".gitignore").write_text(".venv/\n*.spec\ncustom-line\n", encoding="utf-8")
    freeze(proj, monkeypatch)

    lines = (proj / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "*.spec" not in lines
    assert "custom-line" in lines  # user content preserved
    assert "dist/" in lines and "build/" in lines


def test_freeze_is_idempotent_and_respects_edits(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "twice")
    freeze(proj, monkeypatch)
    (proj / "app.spec").write_text("# my edited spec\n", encoding="utf-8")
    freeze(proj, monkeypatch)
    assert (proj / "app.spec").read_text(encoding="utf-8") == "# my edited spec\n"  # not overwritten


def test_freeze_refuses_outside_an_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "freeze"])
    with pytest.raises(SystemExit):
        cli.main()


def test_generated_app_runs_through_full_lifecycle(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch)
    (proj / ".env").write_text("APP_NAME=probe\nTICK_SECONDS=0.05\nRUN_SECONDS=0.4\n", encoding="utf-8")

    env = os.environ | {"PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=proj, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "[ticker] started" in result.stdout
    assert "tick #1" in result.stdout
    assert re.search(r"stopped after \d+ ticks", result.stdout)
    # ordered lifecycle: start precedes ticks, stop is last
    assert result.stdout.index("[ticker] started") < result.stdout.index("tick #1")
    assert result.stdout.rstrip().endswith("ticks")

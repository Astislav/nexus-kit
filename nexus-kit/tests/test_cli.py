import os
import re
import subprocess
import sys
from pathlib import Path

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

    claude_md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    assert ".ai/" in claude_md and "sync-ai" in claude_md  # points at the directory, not one file


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

    assert not (proj / "build.bat").exists()  # building is `nexus-kit build`, not shell scripts
    assert not (proj / "build.sh").exists()

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


def build(proj, monkeypatch, *extra):
    monkeypatch.chdir(proj)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "build", *extra])
    cli.main()


def test_build_refuses_without_spec(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "nospec")
    monkeypatch.chdir(proj)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "build"])
    with pytest.raises(SystemExit):
        cli.main()


def test_build_is_safe_by_default_no_real_env_in_dist(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "safe")
    freeze(proj, monkeypatch)
    (proj / ".env.example").write_text("APP_NAME=\n", encoding="utf-8")
    (proj / "resources").mkdir()
    (proj / "resources" / "hint.png").write_text("img", encoding="utf-8")

    commands = []

    def run():
        commands.append(True)
        Path("dist").mkdir()
        return 0

    monkeypatch.setattr(cli, "_run_pyinstaller", run, raising=True)
    build(proj, monkeypatch)

    assert commands, "pyinstaller was not invoked"
    assert not (proj / "dist" / ".env").exists()          # secrets never ship by default
    assert (proj / "dist" / ".env.example").exists()      # the operator template does
    assert (proj / "dist" / "resources" / "hint.png").exists()


def test_build_env_flag_ships_real_env_deliberately(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "appliance")
    freeze(proj, monkeypatch)

    def run():
        Path("dist").mkdir()
        return 0

    monkeypatch.setattr(cli, "_run_pyinstaller", run, raising=True)
    build(proj, monkeypatch, "--env")

    dist_env = (proj / "dist" / ".env").read_text(encoding="utf-8")
    assert "APP_NAME=appliance" in dist_env  # the scaffold's real .env, shipped on purpose


def test_build_cleans_stale_dist(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "stale")
    freeze(proj, monkeypatch)
    (proj / "dist").mkdir()
    (proj / "dist" / "old-garbage.exe").write_text("", encoding="utf-8")

    def run():
        Path("dist").mkdir()
        return 0

    monkeypatch.setattr(cli, "_run_pyinstaller", run, raising=True)
    build(proj, monkeypatch)
    assert not (proj / "dist" / "old-garbage.exe").exists()


def sync_ai(proj, monkeypatch):
    monkeypatch.chdir(proj)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "sync-ai"])
    cli.main()


def test_sync_ai_mirrors_satellite_guides_and_stamps_them(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "synced")
    monkeypatch.setattr(
        cli, "_installed_ai_guides",
        lambda: {"nexus-kit-fastapi": ("0.9.9", "# fastapi guide\ncontract details\n")},
    )
    sync_ai(proj, monkeypatch)

    mirrored = (proj / ".ai" / "nexus-kit-fastapi.md").read_text(encoding="utf-8")
    assert mirrored.startswith("<!-- nexus-kit sync-ai: nexus-kit-fastapi 0.9.9 ")
    assert "# fastapi guide" in mirrored


def test_sync_ai_refreshes_on_upgrade_and_removes_uninstalled(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "moving")
    monkeypatch.setattr(
        cli, "_installed_ai_guides", lambda: {"nexus-kit-fastapi": ("0.9.9", "old contract\n")}
    )
    sync_ai(proj, monkeypatch)
    monkeypatch.setattr(
        cli, "_installed_ai_guides", lambda: {"nexus-kit-fastapi": ("1.0.0", "new contract\n")}
    )
    sync_ai(proj, monkeypatch)
    mirrored = (proj / ".ai" / "nexus-kit-fastapi.md").read_text(encoding="utf-8")
    assert "1.0.0" in mirrored.split("\n")[0]
    assert "new contract" in mirrored and "old contract" not in mirrored

    monkeypatch.setattr(cli, "_installed_ai_guides", lambda: {})
    sync_ai(proj, monkeypatch)
    assert not (proj / ".ai" / "nexus-kit-fastapi.md").exists()  # uninstalled -> gone
    assert (proj / ".ai" / "nexus-kit.md").exists()  # the kernel cheat sheet stays


def test_sync_ai_never_touches_unstamped_files(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "owned")
    (proj / ".ai" / "notes.md").write_text("my notes\n", encoding="utf-8")
    (proj / ".ai" / "nexus-kit-fastapi.md").write_text("hand-written, no stamp\n", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_installed_ai_guides", lambda: {"nexus-kit-fastapi": ("0.9.9", "packaged guide\n")}
    )
    sync_ai(proj, monkeypatch)

    assert (proj / ".ai" / "notes.md").read_text(encoding="utf-8") == "my notes\n"
    assert (proj / ".ai" / "nexus-kit-fastapi.md").read_text(encoding="utf-8") == "hand-written, no stamp\n"


def test_sync_ai_restores_a_stale_kernel_cheat_sheet(tmp_path, monkeypatch):
    proj = scaffold(tmp_path, monkeypatch, "healed")
    sheet = proj / ".ai" / "nexus-kit.md"
    stamp_line = sheet.read_text(encoding="utf-8").split("\n", 1)[0]
    sheet.write_text(stamp_line + "\nstale body\n", encoding="utf-8")

    monkeypatch.setattr(cli, "_installed_ai_guides", lambda: {})
    sync_ai(proj, monkeypatch)

    healed = sheet.read_text(encoding="utf-8")
    assert "stale body" not in healed
    assert "## Bootstrap" in healed  # the template body is back, at the installed version


def test_sync_ai_refuses_outside_an_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["nexus-kit", "sync-ai"])
    with pytest.raises(SystemExit):
        cli.main()


def test_generated_app_survives_windowed_mode_without_stderr(tmp_path, monkeypatch):
    """Regression: PyInstaller windowed builds (console=False) run with
    sys.stderr = None — an unguarded faulthandler.enable() crashed the
    generated app on its own first line."""
    proj = scaffold(tmp_path, monkeypatch)
    (proj / ".env").write_text("APP_NAME=windowed\nTICK_SECONDS=0.05\nRUN_SECONDS=0.3\n", encoding="utf-8")

    env = os.environ | {"PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, runpy; sys.stderr = None; runpy.run_path('main.py', run_name='__main__')",
        ],
        cwd=proj, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "tick #1" in result.stdout  # the app actually ran, not just imported


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

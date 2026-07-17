from pathlib import Path

from nexus_kit.interfaces import EnvironmentInterface


class Env(EnvironmentInterface):
    NEXUS_TEST_NAME: str = "default"
    NEXUS_TEST_FLAG: bool = False

    def __init__(self, env_path: Path) -> None:
        super().__init__(_env_file=env_path)


def test_env_file_values_override_defaults(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NEXUS_TEST_NAME=from_file\nNEXUS_TEST_FLAG=true\n", encoding="utf-8")
    env = Env(env_file)
    assert env.NEXUS_TEST_NAME == "from_file"
    assert env.NEXUS_TEST_FLAG is True


def test_defaults_apply_without_env_file(tmp_path):
    env = Env(tmp_path / "missing.env")
    assert env.NEXUS_TEST_NAME == "default"
    assert env.NEXUS_TEST_FLAG is False


def test_bom_and_foreign_keys_are_tolerated(tmp_path):
    """Windows editors save .env with a BOM; shared .env files carry other tools' keys."""
    env_file = tmp_path / ".env"
    env_file.write_bytes("NEXUS_TEST_NAME=bom_file\nSOME_OTHER_TOOL_VAR=whatever\n".encode("utf-8-sig"))
    env = Env(env_file)
    assert env.NEXUS_TEST_NAME == "bom_file"

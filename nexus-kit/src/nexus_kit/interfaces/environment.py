from injector import singleton
from pydantic_settings import BaseSettings, SettingsConfigDict


@singleton
class EnvironmentInterface(BaseSettings):
    # utf-8-sig: Windows editors (Notepad) save .env with a BOM — without this the
    # first key silently becomes '﻿KEY' and validation fails with a cryptic error.
    # extra="ignore": .env files often carry keys for other tools (compose, direnv).
    model_config = SettingsConfigDict(env_file_encoding="utf-8-sig", extra="ignore")

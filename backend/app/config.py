import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCR_", env_file=".env", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8114
    temp_dir: Path = Path("/tmp/ocrapp")
    job_ttl_seconds: int = 3600
    job_timeout_seconds: int = 1800
    max_upload_mb: int = 200
    max_workers: int = Field(default_factory=lambda: os.cpu_count() or 1)
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

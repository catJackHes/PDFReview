from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_env: Literal["development", "production"] = "development"
    secret_key: str = Field(default="change-me")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    admin_username: str = "admin"
    admin_password: str = "admin123"

    database_url: str = "sqlite:///./pdfreview.db"
    redis_url: str = "redis://localhost:6379/0"

    upload_dir: str = "./storage/uploads"
    render_dir: str = "./storage/render"
    report_dir: str = "./storage/reports"

    max_file_size: int = 10 * 1024 * 1024
    max_pages: int = 200
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_root(self) -> Path:
        return Path(__file__).resolve().parent.parent / "storage"


settings = Settings()

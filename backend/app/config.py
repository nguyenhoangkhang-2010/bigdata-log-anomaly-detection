from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOGAD_", env_file=".env", extra="ignore")

    data_source: str = "demo"  # demo | elasticsearch
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    demo_seed: int = 7
    demo_blocks: int = 4000
    elasticsearch_url: str = "http://localhost:9200"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

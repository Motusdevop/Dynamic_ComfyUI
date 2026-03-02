from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./dynamiccomfy.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    comfy_base_image: str = "ghcr.io/ai-dock/comfyui:latest"
    comfy_internal_port: int = 8188
    comfy_container_models_dir: str = "/opt/ComfyUI/models"
    comfy_container_user_dir: str = "/opt/ComfyUI/user"
    comfy_container_output_dir: str = "/opt/ComfyUI/output"
    comfy_container_temp_dir: str = "/opt/ComfyUI/temp"
    server_public_host: str = "127.0.0.1"
    enable_gpu: bool = False
    comfy_start_timeout_seconds: int = 120

    port_range_start: int = 8101
    port_range_end: int = 8199

    shared_models_dir: str = "/app/data/shared_models"
    users_data_dir: str = "/app/data/users"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def shared_models_path(self) -> Path:
        return Path(self.shared_models_dir)

    @property
    def users_data_path(self) -> Path:
        return Path(self.users_data_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()

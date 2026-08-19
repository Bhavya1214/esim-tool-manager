from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    config_dir: Path = Path.home() / ".esim_tool_manager"
    tools_config: Path = Path(__file__).parent.parent.parent / "config" / "tools.yaml"
    log_dir: Path = Path.home() / ".esim_tool_manager" / "logs"

    auto_confirm: bool = False
    parallel_jobs: int = 4


settings = Settings()

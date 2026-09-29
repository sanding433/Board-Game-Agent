from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model_fast: str = "deepseek-chat"
    model_reasoning: str = "deepseek-reasoner"
    reply_language: str = "zh"
    auto_advise_after_say: bool = False
    sessions_dir: Path = Path("sessions")

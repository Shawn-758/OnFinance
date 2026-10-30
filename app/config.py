from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_name: str = "Adams Onboarding Prototype"
    app_env: str = "dev"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "your_password"
    mysql_database: str = "adams_onboarding"
    database_url: str | None = None

    upload_dir: str = str(ROOT_DIR / "uploads")
    tesseract_cmd: str = ""
    blur_threshold: float = 80.0

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

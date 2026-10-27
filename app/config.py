"""Application settings.

Values can be overridden with environment variables prefixed with LAGERFLOW_,
e.g. LAGERFLOW_DATABASE_URL=sqlite:///./other.db
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAGERFLOW_", env_file=".env")

    database_url: str = "sqlite:///./lagerflow.db"


settings = Settings()

"""Application settings.

Values can be overridden with environment variables prefixed with LAGERFLOW_,
e.g. LAGERFLOW_DATABASE_URL=sqlite:///./other.db
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAGERFLOW_", env_file=".env")

    database_url: str = "sqlite:///./lagerflow.db"

    # Public demo (see app/demo.py). Off by default, so local development is unaffected.
    demo_mode: bool = False
    demo_reset_minutes: int = 60
    demo_max_products: int = 60
    demo_max_movements: int = 2000
    demo_write_limit_per_minute: int = 20
    demo_global_write_limit_per_minute: int = 120


settings = Settings()

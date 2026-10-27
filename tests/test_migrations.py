"""The Alembic migrations must build the same schema as the ORM models."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def alembic_config(db_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def test_upgrade_creates_tables_and_downgrade_removes_them(tmp_path):
    db_path = tmp_path / "migrations.db"
    config = alembic_config(db_path)
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    command.upgrade(config, "head")
    assert {"products", "stock_movements"} <= set(inspect(engine).get_table_names())

    command.downgrade(config, "base")
    assert "products" not in inspect(engine).get_table_names()
    engine.dispose()


def test_models_and_migrations_are_in_sync(tmp_path):
    config = alembic_config(tmp_path / "check.db")
    command.upgrade(config, "head")

    # Raises if autogenerate would detect differences, i.e. a migration is missing.
    command.check(config)

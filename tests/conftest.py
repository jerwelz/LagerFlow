"""Shared test fixtures.

Every test gets a fresh in-memory SQLite database, so tests never affect each other
and never touch the real lagerflow.db file.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.database import Base, get_db
from app.main import app
from app.models import Product


@pytest.fixture
def engine() -> Iterator[Engine]:
    # StaticPool reuses a single connection. Without it, every new connection
    # to "sqlite://" would open a different, empty in-memory database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """API client whose requests use the test database instead of the real one."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    """Factory that inserts a product directly into the database.

    Usage: make_product(sku="ABC-1", current_stock=5)
    """
    counter = 0

    def _make_product(**overrides) -> Product:
        nonlocal counter
        counter += 1
        data = {"sku": f"SKU-{counter:04d}", "name": f"Test product {counter}"}
        data.update(overrides)
        product = Product(**data)
        db_session.add(product)
        db_session.commit()
        return product

    return _make_product

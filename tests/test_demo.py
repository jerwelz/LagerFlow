"""Demo mode: seed data, reset safety, write limits and serving the dashboard."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import Base, get_db
from app.demo import SEED_PRODUCTS, ensure_demo_database, reset_demo_data, stock_from_movements
from app.main import create_app
from app.models import MovementType, Product, StockMovement


def demo_settings(db_path: Path, **overrides) -> Settings:
    values = {"demo_mode": True, "database_url": f"sqlite:///{db_path.as_posix()}"}
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def demo_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'lagerflow-demo.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def make_demo_client(tmp_path: Path, demo_engine: Engine) -> Iterator[Callable[..., TestClient]]:
    """Builds a demo-mode app on the temporary demo database."""
    clients: list[TestClient] = []

    def _make(**overrides) -> TestClient:
        settings = demo_settings(tmp_path / "lagerflow-demo.db", **overrides)
        app = create_app(settings, demo_engine, frontend_dir=tmp_path / "no-frontend")
        session_factory = sessionmaker(bind=demo_engine, autoflush=False, expire_on_commit=False)

        def get_demo_db():
            with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = get_demo_db
        client = TestClient(app)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()


def balances(engine: Engine) -> dict[str, tuple[int, int, bool]]:
    """sku -> (current_stock, IN minus OUT from the history, is_active)"""
    with Session(engine) as session:
        result = {}
        for product in session.scalars(select(Product)):
            movements = session.scalars(
                select(StockMovement)
                .where(StockMovement.product_id == product.id)
                .order_by(StockMovement.created_at)
            ).all()
            running = 0
            for movement in movements:
                running += (
                    movement.quantity
                    if movement.movement_type is MovementType.IN
                    else -movement.quantity
                )
                assert running >= 0, f"{product.sku} goes negative in its history"
            result[product.sku] = (product.current_stock, running, product.is_active)
        return result


# --- seed data ------------------------------------------------------------------


def test_seed_stock_matches_movement_history(tmp_path, demo_engine):
    reset_demo_data(demo_settings(tmp_path / "lagerflow-demo.db"), demo_engine)

    result = balances(demo_engine)

    assert len(result) == len(SEED_PRODUCTS)
    for sku, (current_stock, from_history, _active) in result.items():
        assert current_stock == from_history, sku


def test_seed_covers_normal_low_empty_and_inactive_products():
    states = set()
    for seed in SEED_PRODUCTS:
        stock = stock_from_movements(seed.movements)
        if not seed.is_active:
            states.add("inactive")
        elif stock == 0:
            states.add("empty")
        elif stock < seed.min_stock:
            states.add("low")
        else:
            states.add("normal")
    assert states == {"normal", "low", "empty", "inactive"}


def test_seed_contains_in_and_out_movements():
    types = {movement[1] for seed in SEED_PRODUCTS for movement in seed.movements}
    assert types == {MovementType.IN, MovementType.OUT}


def test_stock_from_movements_rejects_negative_history():
    with pytest.raises(ValueError):
        stock_from_movements(((2, MovementType.IN, 1, "x"), (1, MovementType.OUT, 2, "y")))


def test_reset_is_idempotent_and_removes_user_changes(tmp_path, demo_engine):
    settings = demo_settings(tmp_path / "lagerflow-demo.db")
    reset_demo_data(settings, demo_engine)
    first = balances(demo_engine)
    with Session(demo_engine) as session, session.begin():
        session.add(Product(sku="USER-1", name="Added by a visitor"))

    reset_demo_data(settings, demo_engine)
    reset_demo_data(settings, demo_engine)

    assert balances(demo_engine) == first
    with Session(demo_engine) as session:
        assert session.scalar(select(func.count()).select_from(Product)) == len(SEED_PRODUCTS)


# --- reset guard ----------------------------------------------------------------


def test_reset_refuses_when_demo_mode_is_off(tmp_path, demo_engine):
    settings = demo_settings(tmp_path / "lagerflow-demo.db", demo_mode=False)

    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        reset_demo_data(settings, demo_engine)


def test_reset_refuses_a_database_without_demo_in_its_name(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'lagerflow.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.add(Product(sku="REAL-1", name="Real product"))

    with pytest.raises(RuntimeError, match="demo"):
        reset_demo_data(demo_settings(tmp_path / "lagerflow.db"), engine)

    with Session(engine) as session:
        assert session.scalar(select(Product.sku)) == "REAL-1"
    engine.dispose()


def test_reset_refuses_in_memory_database():
    engine = create_engine("sqlite://")
    with pytest.raises(RuntimeError):
        ensure_demo_database(Settings(demo_mode=True), engine)


# --- demo mode in the API -------------------------------------------------------


def test_demo_app_starts_with_seed_data(make_demo_client):
    client = make_demo_client()

    summary = client.get("/inventory/summary").json()

    active = [seed for seed in SEED_PRODUCTS if seed.is_active]
    assert summary["active_products"] == len(active)
    assert summary["total_units"] == sum(stock_from_movements(s.movements) for s in active)
    assert summary["out_of_stock_products"] >= 1
    assert summary["low_stock_products"] >= 1


def test_demo_info_describes_limits(make_demo_client):
    response = make_demo_client(demo_max_products=42).get("/demo/info")

    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is True
    assert body["limits"]["max_products"] == 42
    assert body["next_reset_at"]


def test_writes_are_rate_limited_per_client(make_demo_client):
    client = make_demo_client(demo_write_limit_per_minute=3)
    product_id = client.get("/products").json()["items"][0]["id"]
    payload = {"movement_type": "IN", "quantity": 1}

    statuses = [
        client.post(f"/products/{product_id}/movements", json=payload).status_code for _ in range(4)
    ]

    assert statuses == [201, 201, 201, 429]
    response = client.post(f"/products/{product_id}/movements", json=payload)
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) >= 1


def test_rate_limit_is_tracked_per_forwarded_client(make_demo_client):
    client = make_demo_client(demo_write_limit_per_minute=1)
    payload = {"sku": "NEW-1", "name": "Neu"}

    first = client.post("/products", json=payload, headers={"X-Forwarded-For": "1.1.1.1"})
    # A spoofed first hop does not help: the proxy-appended last hop counts.
    second = client.post(
        "/products",
        json={"sku": "NEW-2", "name": "Neu"},
        headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"},
    )
    other = client.post(
        "/products", json={"sku": "NEW-3", "name": "Neu"}, headers={"X-Forwarded-For": "2.2.2.2"}
    )

    assert (first.status_code, second.status_code, other.status_code) == (201, 429, 201)


def test_rate_limit_uses_cloudflare_client_ip_when_present(make_demo_client):
    # On Render the last X-Forwarded-For hop is a changing proxy address; the
    # visitor is identified by CF-Connecting-IP, which Cloudflare overwrites.
    client = make_demo_client(demo_write_limit_per_minute=1)

    def post(sku: str, visitor: str, proxy: str):
        headers = {"CF-Connecting-IP": visitor, "X-Forwarded-For": f"{visitor}, {proxy}"}
        return client.post("/products", json={"sku": sku, "name": "Neu"}, headers=headers)

    first = post("CF-1", "203.0.113.5", "10.0.0.1")
    same_visitor_other_proxy = post("CF-2", "203.0.113.5", "10.0.0.2")
    other_visitor = post("CF-3", "198.51.100.7", "10.0.0.3")

    assert (first.status_code, same_visitor_other_proxy.status_code, other_visitor.status_code) == (
        201,
        429,
        201,
    )


def test_global_write_limit_applies_across_clients(make_demo_client):
    client = make_demo_client(demo_global_write_limit_per_minute=2)

    statuses = [
        client.post(
            "/products",
            json={"sku": f"G-{i}", "name": "Neu"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(3)
    ]

    assert statuses == [201, 201, 429]


def test_reads_are_not_rate_limited(make_demo_client):
    client = make_demo_client(demo_write_limit_per_minute=1)

    assert all(client.get("/products").status_code == 200 for _ in range(10))


def test_product_cap_returns_conflict(make_demo_client):
    client = make_demo_client(demo_max_products=len(SEED_PRODUCTS))

    response = client.post("/products", json={"sku": "ONE-TOO-MANY", "name": "Neu"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DEMO_LIMIT_REACHED"


def test_movement_cap_returns_conflict(make_demo_client):
    total_seed_movements = sum(len(seed.movements) for seed in SEED_PRODUCTS)
    client = make_demo_client(demo_max_movements=total_seed_movements)
    product_id = client.get("/products").json()["items"][0]["id"]

    response = client.post(
        f"/products/{product_id}/movements", json={"movement_type": "IN", "quantity": 1}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DEMO_LIMIT_REACHED"


def test_negative_stock_is_still_impossible_in_demo_mode(make_demo_client):
    client = make_demo_client()
    product = client.get("/products", params={"search": "EL-LED-P12"}).json()["items"][0]
    assert product["current_stock"] == 0

    response = client.post(
        f"/products/{product['id']}/movements", json={"movement_type": "OUT", "quantity": 1}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"


def test_due_reset_restores_seed_data(make_demo_client, demo_engine):
    client = make_demo_client()
    client.post("/products", json={"sku": "TEMP-1", "name": "Temporär"})
    state = client.app.state.demo
    state.next_reset_at = state.next_reset_at.replace(year=2000)

    response = client.get("/products", params={"search": "TEMP-1"})

    assert response.json()["total"] == 0


# --- demo mode off (default) ----------------------------------------------------


def test_demo_endpoints_absent_without_demo_mode(client):
    assert client.get("/demo/info").status_code == 404


def test_no_rate_limit_without_demo_mode(client):
    statuses = {
        client.post("/products", json={"sku": f"P-{i}", "name": "x"}).status_code for i in range(30)
    }
    assert statuses == {201}


def test_default_settings_do_not_enable_demo_mode(monkeypatch):
    monkeypatch.delenv("LAGERFLOW_DEMO_MODE", raising=False)
    assert Settings(_env_file=None).demo_mode is False


# --- serving the dashboard ------------------------------------------------------


@pytest.fixture
def frontend_app(tmp_path: Path) -> FastAPI:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>LagerFlow</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("do not serve", encoding="utf-8")
    return create_app(Settings(_env_file=None), frontend_dir=dist)


def test_root_serves_dashboard_when_built(frontend_app):
    with TestClient(frontend_app) as client:
        root = client.get("/")
        asset = client.get("/assets/app.js")

    assert root.status_code == 200
    assert "<title>LagerFlow</title>" in root.text
    assert asset.status_code == 200


def test_unknown_paths_keep_json_errors_and_files_outside_dist_are_hidden(frontend_app):
    with TestClient(frontend_app) as client:
        unknown = client.get("/does-not-exist")
        outside = client.get("/assets/../../secret.txt")
        secret = client.get("/secret.txt")

    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "HTTP_ERROR"
    assert outside.status_code == 404
    assert secret.status_code == 404


def test_root_is_not_found_without_build(tmp_path):
    with TestClient(create_app(Settings(_env_file=None), frontend_dir=tmp_path)) as client:
        assert client.get("/").status_code == 404

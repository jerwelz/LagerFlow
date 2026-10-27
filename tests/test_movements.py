"""API tests for POST /products/{id}/movements."""

import pytest
from sqlalchemy import func, select

from app.models import StockMovement


def post_movement(client, product_id, movement_type="IN", quantity=1, **extra):
    payload = {"movement_type": movement_type, "quantity": quantity, **extra}
    return client.post(f"/products/{product_id}/movements", json=payload)


def stock_of(client, product_id) -> int:
    return client.get(f"/products/{product_id}").json()["current_stock"]


def movement_count(db_session) -> int:
    return db_session.scalar(select(func.count(StockMovement.id)))


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- Successful movements --------------------------------------------------------


def test_incoming_movement_increases_stock(client, make_product):
    product = make_product(current_stock=2)

    response = post_movement(client, product.id, "IN", 10, reason="Delivery #42")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["product_id"] == product.id
    assert body["movement_type"] == "IN"
    assert body["quantity"] == 10
    assert body["reason"] == "Delivery #42"
    assert body["created_at"]
    assert stock_of(client, product.id) == 12


def test_outgoing_movement_decreases_stock(client, make_product):
    product = make_product(current_stock=10)

    response = post_movement(client, product.id, "OUT", 4)

    assert response.status_code == 201
    assert response.json()["movement_type"] == "OUT"
    assert stock_of(client, product.id) == 6


def test_outgoing_movement_can_take_the_entire_stock(client, make_product):
    product = make_product(current_stock=5)

    response = post_movement(client, product.id, "OUT", 5)

    assert response.status_code == 201
    assert stock_of(client, product.id) == 0


def test_reason_is_optional_and_trimmed(client, make_product):
    product = make_product()

    without = post_movement(client, product.id)
    trimmed = post_movement(client, product.id, reason="  Inventory count  ")

    assert without.json()["reason"] is None
    assert trimmed.json()["reason"] == "Inventory count"


def test_every_movement_is_stored_and_matches_the_stock(client, db_session, make_product):
    product = make_product()
    steps = [("IN", 10), ("OUT", 3), ("IN", 5), ("OUT", 12)]

    for movement_type, quantity in steps:
        assert post_movement(client, product.id, movement_type, quantity).status_code == 201

    movements = db_session.scalars(
        select(StockMovement).where(StockMovement.product_id == product.id)
    ).all()
    ins = sum(m.quantity for m in movements if m.movement_type == "IN")
    outs = sum(m.quantity for m in movements if m.movement_type == "OUT")
    assert len(movements) == len(steps)
    assert stock_of(client, product.id) == ins - outs == 0


def test_movements_only_change_their_own_product(client, make_product):
    target = make_product(current_stock=5)
    other = make_product(current_stock=5)

    post_movement(client, target.id, "OUT", 2)

    assert stock_of(client, target.id) == 3
    assert stock_of(client, other.id) == 5


# --- Business rule violations (409) ----------------------------------------------


def test_outgoing_more_than_available_returns_409(client, db_session, make_product):
    product = make_product(current_stock=3)

    response = post_movement(client, product.id, "OUT", 5)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"] == {"requested": 5, "available": 3}
    assert stock_of(client, product.id) == 3
    assert movement_count(db_session) == 0


def test_outgoing_from_empty_stock_returns_409(client, make_product):
    product = make_product(current_stock=0)

    response = post_movement(client, product.id, "OUT", 1)

    assert response.status_code == 409
    assert error_code(response) == "INSUFFICIENT_STOCK"


@pytest.mark.parametrize("movement_type", ["IN", "OUT"])
def test_inactive_product_rejects_movements(client, db_session, make_product, movement_type):
    product = make_product(current_stock=5, is_active=False)

    response = post_movement(client, product.id, movement_type, 1)

    assert response.status_code == 409
    assert error_code(response) == "PRODUCT_INACTIVE"
    assert stock_of(client, product.id) == 5
    assert movement_count(db_session) == 0


# --- Not found and invalid input -------------------------------------------------


def test_movement_for_unknown_product_returns_404(client, db_session):
    response = post_movement(client, 999)

    assert response.status_code == 404
    assert error_code(response) == "PRODUCT_NOT_FOUND"
    assert movement_count(db_session) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"movement_type": "IN", "quantity": 0},
        {"movement_type": "IN", "quantity": -5},
        {"movement_type": "IN", "quantity": 1.5},
        {"movement_type": "IN", "quantity": "many"},
        {"movement_type": "IN", "quantity": 1_000_001},
        {"movement_type": "IN"},
        {"quantity": 1},
        {"movement_type": "SIDEWAYS", "quantity": 1},
        {"movement_type": "in", "quantity": 1},
        {"movement_type": "IN", "quantity": 1, "reason": "   "},
        {"movement_type": "IN", "quantity": 1, "reason": "x" * 256},
        {"movement_type": "IN", "quantity": 1, "current_stock": 50},
    ],
)
def test_invalid_movement_returns_422_and_changes_nothing(
    client, db_session, make_product, payload
):
    product = make_product(current_stock=5)

    response = client.post(f"/products/{product.id}/movements", json=payload)

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert stock_of(client, product.id) == 5
    assert movement_count(db_session) == 0


def test_non_numeric_product_id_returns_422(client):
    response = post_movement(client, "abc")

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"

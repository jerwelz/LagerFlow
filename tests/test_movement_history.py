"""API tests for GET /products/{id}/movements."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import MovementType, StockMovement


def post_movement(client, product_id, movement_type="IN", quantity=1, **extra):
    payload = {"movement_type": movement_type, "quantity": quantity, **extra}
    return client.post(f"/products/{product_id}/movements", json=payload)


def history(client, product_id, **params):
    return client.get(f"/products/{product_id}/movements", params=params)


def add_movement_at(db_session, product_id: int, created_at: datetime) -> StockMovement:
    movement = StockMovement(
        product_id=product_id,
        movement_type=MovementType.IN,
        quantity=1,
        created_at=created_at,
    )
    db_session.add(movement)
    db_session.commit()
    return movement


def test_empty_history(client, make_product):
    product = make_product()

    response = history(client, product.id)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_history_returns_recorded_movements(client, make_product):
    product = make_product()
    post_movement(client, product.id, "IN", 10, reason="Delivery")
    post_movement(client, product.id, "OUT", 4)

    body = history(client, product.id).json()

    assert body["total"] == 2
    newest, oldest = body["items"]
    assert (newest["movement_type"], newest["quantity"], newest["reason"]) == ("OUT", 4, None)
    assert (oldest["movement_type"], oldest["quantity"], oldest["reason"]) == ("IN", 10, "Delivery")
    assert set(newest) == {"id", "product_id", "movement_type", "quantity", "reason", "created_at"}


def test_history_is_sorted_newest_first_by_timestamp(client, db_session, make_product):
    product = make_product()
    now = datetime.now(UTC)
    # Inserted out of order on purpose: the id order differs from the time order.
    middle = add_movement_at(db_session, product.id, now - timedelta(hours=1))
    oldest = add_movement_at(db_session, product.id, now - timedelta(days=1))
    newest = add_movement_at(db_session, product.id, now)

    ids = [m["id"] for m in history(client, product.id).json()["items"]]

    assert ids == [newest.id, middle.id, oldest.id]


def test_movements_with_equal_timestamps_are_ordered_by_id(client, db_session, make_product):
    product = make_product()
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    created = [add_movement_at(db_session, product.id, same_time) for _ in range(3)]

    ids = [m["id"] for m in history(client, product.id).json()["items"]]

    assert ids == [m.id for m in reversed(created)]


def test_history_pagination(client, make_product):
    product = make_product()
    for quantity in range(1, 6):
        post_movement(client, product.id, "IN", quantity)

    all_ids = [m["id"] for m in history(client, product.id, limit=100).json()["items"]]
    first = history(client, product.id, limit=2, offset=0).json()
    second = history(client, product.id, limit=2, offset=2).json()
    third = history(client, product.id, limit=2, offset=4).json()
    beyond = history(client, product.id, limit=2, offset=10).json()

    pages = [first, second, third]
    assert [m["id"] for page in pages for m in page["items"]] == all_ids
    assert [len(page["items"]) for page in pages] == [2, 2, 1]
    assert all(page["total"] == 5 for page in pages + [beyond])
    assert (second["limit"], second["offset"]) == (2, 2)
    assert beyond["items"] == []


def test_history_only_contains_movements_of_the_requested_product(client, make_product):
    product = make_product()
    other = make_product()
    post_movement(client, product.id, "IN", 1)
    post_movement(client, other.id, "IN", 2)
    post_movement(client, other.id, "IN", 3)

    body = history(client, product.id).json()

    assert body["total"] == 1
    assert [m["product_id"] for m in body["items"]] == [product.id]


def test_history_of_inactive_product_is_available(client, make_product):
    product = make_product()
    post_movement(client, product.id, "IN", 5)
    client.post(f"/products/{product.id}/deactivate")

    response = history(client, product.id)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_history_of_unknown_product_returns_404(client):
    response = history(client, 999)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_history_rejects_invalid_pagination(client, make_product, params):
    product = make_product()

    response = history(client, product.id, **params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_history_matches_current_stock(client, make_product):
    product = make_product()
    for movement_type, quantity in [("IN", 20), ("OUT", 5), ("OUT", 7), ("IN", 2)]:
        post_movement(client, product.id, movement_type, quantity)

    items = history(client, product.id, limit=100).json()["items"]
    balance = sum(m["quantity"] if m["movement_type"] == "IN" else -m["quantity"] for m in items)

    assert balance == client.get(f"/products/{product.id}").json()["current_stock"] == 10

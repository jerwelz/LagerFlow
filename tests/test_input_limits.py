"""Integers larger than the database can store must be rejected with 422, not crash with 500.

Python integers have no size limit, but SQLite stores at most signed 64-bit values.
"""

import pytest

from app.schemas import MAX_DB_INTEGER

TOO_BIG = MAX_DB_INTEGER + 1


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"/products/{TOO_BIG}", None),
        ("PATCH", f"/products/{TOO_BIG}", {"name": "x"}),
        ("POST", f"/products/{TOO_BIG}/deactivate", None),
        ("POST", f"/products/{TOO_BIG}/movements", {"movement_type": "IN", "quantity": 1}),
        ("GET", f"/products/{TOO_BIG}/movements", None),
        ("GET", "/products/99999999999999999999999999999999", None),
    ],
)
def test_oversized_product_id_returns_422(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "path",
    [
        f"/products/{MAX_DB_INTEGER}",
        f"/products/{MAX_DB_INTEGER}/movements",
    ],
)
def test_largest_storable_product_id_is_accepted_and_returns_404(client, path):
    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/products", "/products/1/movements"])
def test_oversized_offset_returns_422(client, make_product, path):
    make_product()

    response = client.get(path, params={"offset": TOO_BIG})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_largest_storable_offset_returns_empty_page(client, make_product):
    make_product()

    response = client.get("/products", params={"offset": MAX_DB_INTEGER})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_oversized_min_stock_on_create_returns_422(client):
    response = client.post("/products", json={"sku": "BIG", "name": "Big", "min_stock": TOO_BIG})

    assert response.status_code == 422


def test_oversized_min_stock_on_update_returns_422(client, make_product):
    product = make_product()

    response = client.patch(f"/products/{product.id}", json={"min_stock": TOO_BIG})

    assert response.status_code == 422


def test_largest_storable_min_stock_is_accepted(client):
    response = client.post(
        "/products", json={"sku": "MAX", "name": "Max", "min_stock": MAX_DB_INTEGER}
    )

    assert response.status_code == 201
    assert response.json()["min_stock"] == MAX_DB_INTEGER

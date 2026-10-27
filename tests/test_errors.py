"""Every error must use the same response shape: {"error": {"code", "message", "details"}}.

These tests use a small throwaway app with routes that raise on purpose, because the
real endpoints that raise these errors arrive in later milestones.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import ConflictError, NotFoundError, register_exception_handlers


class Item(BaseModel):
    quantity: int


@pytest.fixture
def error_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/not-found")
    def raise_not_found():
        raise NotFoundError("Product 42 not found.")

    @app.get("/conflict")
    def raise_conflict():
        raise ConflictError(
            "Requested 5, available 3.",
            code="INSUFFICIENT_STOCK",
            details={"requested": 5, "available": 3},
        )

    @app.post("/items")
    def create_item(item: Item):
        return item

    @app.get("/crash")
    def crash():
        raise RuntimeError("boom")

    # raise_server_exceptions=False lets us see the 500 response instead of the exception.
    return TestClient(app, raise_server_exceptions=False)


def assert_error_shape(body: dict) -> dict:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


def test_not_found_error_returns_404(error_client):
    response = error_client.get("/not-found")

    assert response.status_code == 404
    error = assert_error_shape(response.json())
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "Product 42 not found."
    assert error["details"] is None


def test_conflict_error_with_custom_code_and_details(error_client):
    response = error_client.get("/conflict")

    assert response.status_code == 409
    error = assert_error_shape(response.json())
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"] == {"requested": 5, "available": 3}


def test_validation_error_returns_422_in_same_shape(error_client):
    response = error_client.post("/items", json={"quantity": "lots"})

    assert response.status_code == 422
    error = assert_error_shape(response.json())
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["loc"] == ["body", "quantity"]


def test_unknown_route_returns_404_in_same_shape(error_client):
    response = error_client.get("/does-not-exist")

    assert response.status_code == 404
    assert assert_error_shape(response.json())["code"] == "HTTP_ERROR"


def test_wrong_method_returns_405_in_same_shape(error_client):
    response = error_client.delete("/items")

    assert response.status_code == 405
    assert assert_error_shape(response.json())["code"] == "HTTP_ERROR"


def test_unexpected_error_returns_500_without_internal_details(error_client):
    response = error_client.get("/crash")

    assert response.status_code == 500
    error = assert_error_shape(response.json())
    assert error["code"] == "INTERNAL_ERROR"
    assert "boom" not in error["message"]

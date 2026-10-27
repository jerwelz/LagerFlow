"""API tests for /products: create, get, list, update and deactivate."""

import pytest


def create(client, **overrides):
    payload = {"sku": "ABC-1", "name": "Screwdriver", "min_stock": 5}
    payload.update(overrides)
    return client.post("/products", json=payload)


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- POST /products -------------------------------------------------------------


def test_create_product_returns_201_with_product(client):
    response = create(client, description="Phillips, size 2")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["sku"] == "ABC-1"
    assert body["name"] == "Screwdriver"
    assert body["description"] == "Phillips, size 2"
    assert body["min_stock"] == 5
    assert body["current_stock"] == 0
    assert body["is_active"] is True
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")


def test_create_product_normalizes_sku_and_name(client):
    response = create(client, sku="  abc-1 ", name="  Screwdriver  ")

    assert response.status_code == 201
    assert response.json()["sku"] == "ABC-1"
    assert response.json()["name"] == "Screwdriver"


def test_create_product_with_duplicate_sku_returns_409(client):
    create(client, sku="ABC-1")

    response = create(client, sku="abc-1", name="Other product")

    assert response.status_code == 409
    assert error_code(response) == "DUPLICATE_SKU"


def test_create_product_rejects_current_stock(client):
    response = create(client, current_stock=100)

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"name": "x" * 201},
        {"sku": ""},
        {"sku": "has space"},
        {"sku": "-STARTS-WITH-DASH"},
        {"sku": "X" * 51},
        {"min_stock": -1},
        {"min_stock": "many"},
    ],
)
def test_create_product_rejects_invalid_input(client, overrides):
    response = create(client, **overrides)

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


def test_create_product_requires_sku_and_name(client):
    response = client.post("/products", json={})

    assert response.status_code == 422
    missing = {tuple(err["loc"]) for err in response.json()["error"]["details"]}
    assert missing == {("body", "sku"), ("body", "name")}


# --- GET /products/{id} ----------------------------------------------------------


def test_get_product_returns_product(client, make_product):
    product = make_product(sku="GET-1", name="Hammer")

    response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["sku"] == "GET-1"


def test_get_unknown_product_returns_404(client):
    response = client.get("/products/999")

    assert response.status_code == 404
    assert error_code(response) == "PRODUCT_NOT_FOUND"


def test_get_inactive_product_is_still_possible(client, make_product):
    product = make_product(is_active=False)

    response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


# --- GET /products ---------------------------------------------------------------


def test_list_products_returns_items_and_metadata(client, make_product):
    make_product()
    make_product()

    response = client.get("/products")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_list_products_is_empty_without_products(client):
    body = client.get("/products").json()

    assert body["items"] == []
    assert body["total"] == 0


def test_list_products_paginates_in_stable_order(client, make_product):
    ids = [make_product().id for _ in range(5)]

    first = client.get("/products", params={"limit": 2, "offset": 0}).json()
    second = client.get("/products", params={"limit": 2, "offset": 2}).json()
    last = client.get("/products", params={"limit": 2, "offset": 4}).json()

    assert [p["id"] for p in first["items"]] == ids[0:2]
    assert [p["id"] for p in second["items"]] == ids[2:4]
    assert [p["id"] for p in last["items"]] == ids[4:5]
    assert first["total"] == second["total"] == last["total"] == 5


def test_list_products_searches_name_and_sku_case_insensitively(client, make_product):
    make_product(sku="TOOL-1", name="Claw Hammer")
    make_product(sku="HAM-2", name="Rubber mallet")
    make_product(sku="NAIL-3", name="Nails 40mm")

    body = client.get("/products", params={"search": "ham"}).json()

    assert {p["sku"] for p in body["items"]} == {"TOOL-1", "HAM-2"}
    assert body["total"] == 2


def test_list_products_search_treats_wildcards_literally(client, make_product):
    make_product(name="Discount 50% pack")
    make_product(name="Regular pack")

    body = client.get("/products", params={"search": "50%"}).json()

    assert [p["name"] for p in body["items"]] == ["Discount 50% pack"]


def test_list_products_hides_inactive_by_default(client, make_product):
    make_product(sku="ACTIVE")
    make_product(sku="OLD", is_active=False)

    default = client.get("/products").json()
    everything = client.get("/products", params={"include_inactive": True}).json()

    assert [p["sku"] for p in default["items"]] == ["ACTIVE"]
    assert default["total"] == 1
    assert {p["sku"] for p in everything["items"]} == {"ACTIVE", "OLD"}
    assert everything["total"] == 2


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"search": "x" * 101}]
)
def test_list_products_rejects_invalid_query_parameters(client, params):
    response = client.get("/products", params=params)

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


# --- PATCH /products/{id} --------------------------------------------------------


def test_update_product_changes_only_sent_fields(client, make_product):
    product = make_product(sku="UPD-1", name="Old name", description="Keep me", min_stock=3)

    response = client.patch(f"/products/{product.id}", json={"name": "New name"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New name"
    assert body["sku"] == "UPD-1"
    assert body["description"] == "Keep me"
    assert body["min_stock"] == 3


def test_update_product_can_change_min_stock_and_clear_description(client, make_product):
    product = make_product(description="Temporary")

    response = client.patch(f"/products/{product.id}", json={"min_stock": 10, "description": None})

    assert response.status_code == 200
    assert response.json()["min_stock"] == 10
    assert response.json()["description"] is None


def test_update_product_persists_changes(client, make_product):
    product = make_product()

    client.patch(f"/products/{product.id}", json={"name": "Saved"})

    assert client.get(f"/products/{product.id}").json()["name"] == "Saved"


def test_update_product_can_change_sku(client, make_product):
    product = make_product(sku="OLD-SKU")

    response = client.patch(f"/products/{product.id}", json={"sku": "new-sku"})

    assert response.status_code == 200
    assert response.json()["sku"] == "NEW-SKU"


def test_update_product_to_existing_sku_returns_409(client, make_product):
    make_product(sku="TAKEN")
    product = make_product(sku="MINE")

    response = client.patch(f"/products/{product.id}", json={"sku": "taken"})

    assert response.status_code == 409
    assert error_code(response) == "DUPLICATE_SKU"


def test_update_product_with_its_own_sku_is_allowed(client, make_product):
    product = make_product(sku="SAME")

    response = client.patch(f"/products/{product.id}", json={"sku": "SAME", "name": "Renamed"})

    assert response.status_code == 200


@pytest.mark.parametrize("field", ["current_stock", "is_active", "id", "created_at"])
def test_update_product_rejects_read_only_fields(client, make_product, field):
    product = make_product(current_stock=7)

    response = client.patch(f"/products/{product.id}", json={field: 0})

    assert response.status_code == 422
    assert client.get(f"/products/{product.id}").json()["current_stock"] == 7


@pytest.mark.parametrize("field", ["sku", "name", "min_stock"])
def test_update_product_rejects_null_for_required_fields(client, make_product, field):
    product = make_product()

    response = client.patch(f"/products/{product.id}", json={field: None})

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


def test_update_unknown_product_returns_404(client):
    response = client.patch("/products/999", json={"name": "Ghost"})

    assert response.status_code == 404
    assert error_code(response) == "PRODUCT_NOT_FOUND"


# --- POST /products/{id}/deactivate ----------------------------------------------


def test_deactivate_product(client, make_product):
    product = make_product(current_stock=4)

    response = client.post(f"/products/{product.id}/deactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["current_stock"] == 4
    assert client.get("/products").json()["total"] == 0


def test_deactivate_is_idempotent(client, make_product):
    product = make_product()

    client.post(f"/products/{product.id}/deactivate")
    response = client.post(f"/products/{product.id}/deactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_deactivate_unknown_product_returns_404(client):
    response = client.post("/products/999/deactivate")

    assert response.status_code == 404
    assert error_code(response) == "PRODUCT_NOT_FOUND"


def test_products_cannot_be_deleted(client, make_product):
    product = make_product()

    response = client.delete(f"/products/{product.id}")

    assert response.status_code == 405

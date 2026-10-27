"""Service-level tests for rules that are hard to trigger through the API."""

import pytest

from app.errors import ConflictError
from app.schemas import ProductCreate
from app.services import products as product_service


def test_duplicate_sku_is_caught_even_if_the_pre_check_misses_it(
    db_session, make_product, monkeypatch
):
    """Simulates two requests creating the same SKU at the same moment.

    Both pass the "is the SKU free?" check; the database's unique index must
    still stop the second one, and the service must turn that into a 409.
    """
    make_product(sku="RACE-1")
    monkeypatch.setattr(product_service, "_ensure_sku_is_free", lambda db, sku: None)

    with pytest.raises(ConflictError) as exc_info:
        product_service.create_product(db_session, ProductCreate(sku="RACE-1", name="Second"))

    assert exc_info.value.code == "DUPLICATE_SKU"
    # The failed transaction was rolled back, so the session is usable again.
    assert product_service.get_product(db_session, 1).sku == "RACE-1"

"""Database-level rules: defaults, constraints and relationships.

These constraints are the last safety net. Later milestones add friendlier checks
in the service layer, but the database must reject bad data on its own too.
"""

from datetime import UTC

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import MovementType, StockMovement


def test_sqlite_foreign_keys_are_enabled(db_session):
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_product_defaults(make_product):
    product = make_product()

    assert product.id is not None
    assert product.current_stock == 0
    assert product.min_stock == 0
    assert product.is_active is True
    assert product.description is None


def test_created_at_is_timezone_aware_utc(db_session, make_product):
    product = make_product()
    db_session.expire_all()  # force a fresh load from the database

    assert product.created_at.tzinfo == UTC


def test_duplicate_sku_is_rejected(db_session, make_product):
    make_product(sku="ABC-1")

    with pytest.raises(IntegrityError):
        make_product(sku="ABC-1")
    db_session.rollback()


@pytest.mark.parametrize("field", ["current_stock", "min_stock"])
def test_negative_stock_values_are_rejected(db_session, make_product, field):
    with pytest.raises(IntegrityError):
        make_product(**{field: -1})
    db_session.rollback()


def add_movement(db_session, **overrides) -> StockMovement:
    data = {"movement_type": MovementType.IN, "quantity": 1}
    data.update(overrides)
    movement = StockMovement(**data)
    db_session.add(movement)
    db_session.commit()
    return movement


def test_movement_is_linked_to_product(db_session, make_product):
    product = make_product()
    movement = add_movement(db_session, product_id=product.id, quantity=5, reason="Delivery")

    assert movement.product.sku == product.sku
    assert product.movements == [movement]
    assert movement.created_at.tzinfo == UTC


@pytest.mark.parametrize("quantity", [0, -3])
def test_movement_quantity_must_be_positive(db_session, make_product, quantity):
    product = make_product()

    with pytest.raises(IntegrityError):
        add_movement(db_session, product_id=product.id, quantity=quantity)
    db_session.rollback()


def test_movement_type_only_allows_in_and_out(db_session, make_product):
    product = make_product()

    # Raw SQL bypasses the Python enum, so this proves the database CHECK works.
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO stock_movements (product_id, movement_type, quantity, created_at) "
                "VALUES (:pid, 'SIDEWAYS', 1, CURRENT_TIMESTAMP)"
            ),
            {"pid": product.id},
        )
    db_session.rollback()


def test_movement_for_unknown_product_is_rejected(db_session):
    with pytest.raises(IntegrityError):
        add_movement(db_session, product_id=999)
    db_session.rollback()


def test_product_with_movements_cannot_be_deleted(db_session, make_product):
    product = make_product()
    add_movement(db_session, product_id=product.id)

    with pytest.raises(IntegrityError):
        db_session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product.id})
    db_session.rollback()

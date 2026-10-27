"""Service-level tests for atomicity and concurrency of stock movements.

These situations are hard or impossible to trigger through a single API request,
so the tests call the service directly and simulate the failure or the race.
"""

import threading

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.errors import ConflictError
from app.models import MovementType, Product, StockMovement
from app.repositories import movements as movement_repo
from app.schemas import StockMovementCreate
from app.services import stock as stock_service


def movement(movement_type: MovementType, quantity: int) -> StockMovementCreate:
    return StockMovementCreate(movement_type=movement_type, quantity=quantity)


def stock_in_database(db_session, product_id: int) -> int:
    # Raw SQL, so we read the committed value and not a cached Python object.
    return db_session.execute(
        text("SELECT current_stock FROM products WHERE id = :id"), {"id": product_id}
    ).scalar_one()


def movement_count(db_session) -> int:
    return db_session.scalar(select(func.count(StockMovement.id)))


# --- Atomicity: stock update and movement record succeed or fail together ---------


@pytest.mark.parametrize("movement_type", [MovementType.IN, MovementType.OUT])
def test_stock_is_rolled_back_if_saving_the_movement_fails(
    db_session, make_product, monkeypatch, movement_type
):
    product = make_product(current_stock=10)

    def failing_add(db, new_movement):
        raise RuntimeError("Simulated failure after the stock was already updated")

    monkeypatch.setattr(movement_repo, "add", failing_add)

    with pytest.raises(RuntimeError):
        stock_service.record_movement(db_session, product.id, movement(movement_type, 4))

    assert stock_in_database(db_session, product.id) == 10
    assert movement_count(db_session) == 0


def test_stock_is_rolled_back_if_the_database_rejects_the_movement(
    db_session, make_product, monkeypatch
):
    """The failure happens in the database itself, during commit (foreign key violation)."""
    product = make_product(current_stock=10)
    original_add = movement_repo.add

    def add_with_broken_foreign_key(db, new_movement):
        new_movement.product_id = 999
        original_add(db, new_movement)

    monkeypatch.setattr(movement_repo, "add", add_with_broken_foreign_key)

    with pytest.raises(IntegrityError):
        stock_service.record_movement(db_session, product.id, movement(MovementType.OUT, 4))

    assert stock_in_database(db_session, product.id) == 10
    assert movement_count(db_session) == 0


def test_session_is_usable_after_a_failed_movement(db_session, make_product):
    product = make_product(current_stock=1)

    with pytest.raises(ConflictError):
        stock_service.record_movement(db_session, product.id, movement(MovementType.OUT, 5))
    stock_service.record_movement(db_session, product.id, movement(MovementType.IN, 2))

    assert stock_in_database(db_session, product.id) == 3
    assert movement_count(db_session) == 1


# --- Races: the stock changes between the check and the update -------------------


def change_behind_the_sessions_back(db_session, sql: str, product_id: int) -> None:
    """Simulates another request: changes the row without updating the cached Product."""
    db_session.execute(text(sql), {"id": product_id})
    db_session.commit()


def test_conditional_update_catches_stock_taken_by_another_request(db_session, make_product):
    product = make_product(current_stock=5)
    change_behind_the_sessions_back(
        db_session, "UPDATE products SET current_stock = 1 WHERE id = :id", product.id
    )
    assert product.current_stock == 5  # the service will see this outdated value first

    with pytest.raises(ConflictError) as exc_info:
        stock_service.record_movement(db_session, product.id, movement(MovementType.OUT, 3))

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.details == {"requested": 3, "available": 1}
    assert stock_in_database(db_session, product.id) == 1
    assert movement_count(db_session) == 0


def test_conditional_update_catches_product_deactivated_by_another_request(
    db_session, make_product
):
    product = make_product(current_stock=5)
    change_behind_the_sessions_back(
        db_session, "UPDATE products SET is_active = 0 WHERE id = :id", product.id
    )

    with pytest.raises(ConflictError) as exc_info:
        stock_service.record_movement(db_session, product.id, movement(MovementType.IN, 3))

    assert exc_info.value.code == "PRODUCT_INACTIVE"
    assert stock_in_database(db_session, product.id) == 5
    assert movement_count(db_session) == 0


def test_database_rejects_negative_stock_even_without_the_application(db_session, make_product):
    product = make_product(current_stock=2)

    with pytest.raises(IntegrityError):
        change_behind_the_sessions_back(
            db_session, "UPDATE products SET current_stock = -1 WHERE id = :id", product.id
        )
    db_session.rollback()


# --- Real concurrency: many threads, one product ---------------------------------


@pytest.mark.parametrize("skip_pre_check", [False, True], ids=["normal", "database-only"])
def test_concurrent_withdrawals_never_make_stock_negative(tmp_path, monkeypatch, skip_pre_check):
    """20 threads try to take 3 items each from a stock of 10 at the same moment.

    Only 3 can succeed (9 items). Uses a real database file, because each thread
    needs its own connection. In the "database-only" variant the Python check is
    switched off, which proves the conditional UPDATE alone keeps stock >= 0.
    """
    if skip_pre_check:
        monkeypatch.setattr(stock_service, "_ensure_movement_allowed", lambda product, data: None)

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'concurrency.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as db:
        product = Product(sku="RACE-1", name="Last items", current_stock=10)
        db.add(product)
        db.commit()
        product_id = product.id

    thread_count = 20
    start_together = threading.Barrier(thread_count)
    results: list[str] = []
    unexpected: list[BaseException] = []

    def withdraw() -> None:
        start_together.wait()
        with session_factory() as db:
            try:
                stock_service.record_movement(db, product_id, movement(MovementType.OUT, 3))
                results.append("ok")
            except ConflictError:
                results.append("conflict")
            except BaseException as exc:  # collected and reported by the main thread
                unexpected.append(exc)

    threads = [threading.Thread(target=withdraw) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with session_factory() as db:
        final_stock = db.get(Product, product_id).current_stock
        movements = db.scalars(select(StockMovement)).all()
    engine.dispose()

    assert unexpected == []
    assert results.count("ok") == 3
    assert results.count("conflict") == thread_count - 3
    assert final_stock == 1
    assert len(movements) == 3
    assert final_stock == 10 - sum(m.quantity for m in movements)


# --- The cached Product must match the database after a movement -------------------


def test_cached_product_matches_database_after_concurrent_change(db_session, make_product):
    """Regression test: SQLAlchemy used to recalculate the stock in Python.

    Another request adds 2 items after our Product was loaded (cached: 5, real: 7).
    Taking out 3 must leave the cached object at 4 (the real value), not 2.
    """
    product = make_product(current_stock=5)
    change_behind_the_sessions_back(
        db_session, "UPDATE products SET current_stock = 7 WHERE id = :id", product.id
    )

    stock_service.record_movement(db_session, product.id, movement(MovementType.OUT, 3))

    assert stock_in_database(db_session, product.id) == 4
    assert product.current_stock == 4


def test_sync_does_not_mark_the_product_as_changed(db_session, make_product):
    product = make_product(current_stock=5)

    stock_service.record_movement(db_session, product.id, movement(MovementType.IN, 1))

    assert product.current_stock == 6
    assert product not in db_session.dirty

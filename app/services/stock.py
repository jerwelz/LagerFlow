"""Business logic for stock movements.

The only way stock changes: every change writes a StockMovement in the same
transaction, so the stock level and the movement history always agree.
"""

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.errors import ConflictError
from app.models import MovementType, Product, StockMovement
from app.repositories import movements as movement_repo
from app.repositories import products as product_repo
from app.schemas import StockMovementCreate
from app.services.products import get_product


def _ensure_movement_allowed(product: Product, data: StockMovementCreate) -> None:
    if not product.is_active:
        raise ConflictError(
            f"Product {product.id} is inactive and cannot receive stock movements.",
            code="PRODUCT_INACTIVE",
        )
    if data.movement_type is MovementType.OUT and data.quantity > product.current_stock:
        raise ConflictError(
            f"Insufficient stock: requested {data.quantity}, available {product.current_stock}.",
            code="INSUFFICIENT_STOCK",
            details={"requested": data.quantity, "available": product.current_stock},
        )


def record_movement(db: Session, product_id: int, data: StockMovementCreate) -> StockMovement:
    product = get_product(db, product_id)  # 404 if it does not exist
    # Step 1: check the rules for a clear error message.
    _ensure_movement_allowed(product, data)

    delta = data.quantity if data.movement_type is MovementType.IN else -data.quantity
    try:
        # Step 2: the conditional UPDATE re-checks the rules inside the database,
        # in case another request changed the product after step 1.
        new_stock = product_repo.change_stock(db, product.id, delta)
        if new_stock is None:
            db.rollback()
            db.refresh(product)
            _ensure_movement_allowed(product, data)  # raises with the up-to-date numbers
            raise ConflictError("Stock changed during the request; please retry.")
        # Keep the Python object in sync with the value the database actually stored.
        # set_committed_value does not mark the object as changed (no extra UPDATE).
        set_committed_value(product, "current_stock", new_stock)

        movement = StockMovement(
            product_id=product.id,
            movement_type=data.movement_type,
            quantity=data.quantity,
            reason=data.reason,
        )
        movement_repo.add(db, movement)
        # Step 3: stock update and movement are saved together, or not at all.
        db.commit()
    except Exception:
        db.rollback()
        raise
    return movement


def list_movements(
    db: Session, product_id: int, *, limit: int, offset: int
) -> tuple[list[StockMovement], int]:
    get_product(db, product_id)  # 404 if it does not exist; inactive products are fine
    items = movement_repo.list_for_product(db, product_id, limit=limit, offset=offset)
    total = movement_repo.count_for_product(db, product_id)
    return items, total

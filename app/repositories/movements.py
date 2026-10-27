"""Database access for stock movements. No business rules and no commits here."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import StockMovement


def add(db: Session, movement: StockMovement) -> None:
    db.add(movement)


def list_for_product(
    db: Session, product_id: int, *, limit: int, offset: int
) -> list[StockMovement]:
    stmt = (
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        # Newest first. Two movements can share a timestamp, so the id breaks the tie
        # and makes the order (and therefore pagination) fully deterministic.
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def count_for_product(db: Session, product_id: int) -> int:
    stmt = select(func.count(StockMovement.id)).where(StockMovement.product_id == product_id)
    return db.scalar(stmt) or 0

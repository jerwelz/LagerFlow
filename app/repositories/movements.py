"""Database access for stock movements. No business rules and no commits here."""

from sqlalchemy.orm import Session

from app.models import StockMovement


def add(db: Session, movement: StockMovement) -> None:
    db.add(movement)

"""Database access for products. No business rules and no commits here."""

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Product


def get_by_id(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def get_by_sku(db: Session, sku: str) -> Product | None:
    return db.scalar(select(Product).where(Product.sku == sku))


def add(db: Session, product: Product) -> None:
    db.add(product)


def change_stock(db: Session, product_id: int, delta: int) -> int | None:
    """Add delta (negative for outgoing stock) in one conditional UPDATE.

    The WHERE clause only matches if the product is active and the result would
    not be negative. The database checks and changes the value in one step, so
    two requests cannot both take the last items. Returns the new stock, or
    None if nothing was updated.
    """
    stmt = (
        update(Product)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Product.current_stock + delta >= 0,
        )
        .values(current_stock=Product.current_stock + delta)
        .returning(Product.current_stock)
    )
    return db.execute(stmt).scalar_one_or_none()


def _apply_filters(stmt: Select, search: str | None, include_inactive: bool) -> Select:
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if search:
        # autoescape=True treats % and _ in the search term as normal characters.
        stmt = stmt.where(
            or_(
                Product.name.icontains(search, autoescape=True),
                Product.sku.icontains(search, autoescape=True),
            )
        )
    return stmt


def list_products(
    db: Session, *, search: str | None, include_inactive: bool, limit: int, offset: int
) -> list[Product]:
    stmt = _apply_filters(select(Product), search, include_inactive)
    # A fixed order is required for pagination to return stable pages.
    stmt = stmt.order_by(Product.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_products(db: Session, *, search: str | None, include_inactive: bool) -> int:
    stmt = _apply_filters(select(func.count(Product.id)), search, include_inactive)
    return db.scalar(stmt) or 0

"""Business logic for products. The service decides when to commit."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import Product
from app.repositories import products as product_repo
from app.schemas import ProductCreate, ProductUpdate


def _duplicate_sku_error(sku: str) -> ConflictError:
    return ConflictError(f"A product with SKU '{sku}' already exists.", code="DUPLICATE_SKU")


def _ensure_sku_is_free(db: Session, sku: str) -> None:
    if product_repo.get_by_sku(db, sku) is not None:
        raise _duplicate_sku_error(sku)


def _commit_product(db: Session, product: Product) -> None:
    """Commit, translating a unique-constraint violation into a 409.

    The SKU check before saving gives a clear error in the normal case. The
    database's unique index still protects against two requests creating
    the same SKU at the same moment; this handles that rare case.
    """
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if product_repo.get_by_sku(db, product.sku) is not None:
            raise _duplicate_sku_error(product.sku) from None
        raise


def get_product(db: Session, product_id: int) -> Product:
    product = product_repo.get_by_id(db, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.", code="PRODUCT_NOT_FOUND")
    return product


def list_products(
    db: Session, *, search: str | None, include_inactive: bool, limit: int, offset: int
) -> tuple[list[Product], int]:
    items = product_repo.list_products(
        db, search=search, include_inactive=include_inactive, limit=limit, offset=offset
    )
    total = product_repo.count_products(db, search=search, include_inactive=include_inactive)
    return items, total


def create_product(db: Session, data: ProductCreate) -> Product:
    _ensure_sku_is_free(db, data.sku)
    product = Product(**data.model_dump())  # current_stock starts at 0
    product_repo.add(db, product)
    _commit_product(db, product)
    return product


def update_product(db: Session, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(db, product_id)
    changes = data.model_dump(exclude_unset=True)

    if "sku" in changes and changes["sku"] != product.sku:
        _ensure_sku_is_free(db, changes["sku"])

    for field, value in changes.items():
        setattr(product, field, value)
    _commit_product(db, product)
    return product


def deactivate_product(db: Session, product_id: int) -> Product:
    """Soft delete: the product stays in the database so its history is kept.

    Deactivating an already inactive product is allowed and changes nothing.
    """
    product = get_product(db, product_id)
    product.is_active = False
    db.commit()
    return product

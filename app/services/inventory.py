"""Inventory monitoring and reporting. Read-only: nothing here changes data."""

import csv
import io

from sqlalchemy.orm import Session

from app.models import Product
from app.repositories import products as product_repo
from app.schemas import InventorySummary, StockLevel

CSV_COLUMNS = ["id", "sku", "name", "description", "current_stock", "min_stock", "is_low"]

# Spreadsheet programs run cells starting with these characters as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def get_stock_levels(db: Session) -> list[Product]:
    return product_repo.list_active(db)


def get_low_stock(db: Session) -> list[Product]:
    """Active products whose stock is strictly below their minimum."""
    return product_repo.list_low_stock(db)


def get_summary(db: Session) -> InventorySummary:
    active, units, low, out_of_stock = product_repo.stock_totals(db)
    return InventorySummary(
        active_products=active,
        total_units=units,
        low_stock_products=low,
        out_of_stock_products=out_of_stock,
    )


def _safe_cell(value: str | None) -> str:
    """Prevents CSV formula injection, e.g. a product named '=HYPERLINK(...)'."""
    if not value:
        return ""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def export_inventory_csv(db: Session) -> str:
    """CSV of all active products, one row per product, sorted by SKU."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for product in product_repo.list_active(db):
        level = StockLevel.model_validate(product)
        writer.writerow(
            [
                product.id,
                product.sku,
                _safe_cell(product.name),
                _safe_cell(product.description),
                product.current_stock,
                product.min_stock,
                str(level.is_low).lower(),
            ]
        )
    return buffer.getvalue()

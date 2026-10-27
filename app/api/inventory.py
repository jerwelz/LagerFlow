"""HTTP routes for inventory monitoring and the CSV report."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response

from app.database import DbSession
from app.schemas import InventorySummary, StockLevel
from app.services import inventory as inventory_service

router = APIRouter()


@router.get("/inventory/levels", response_model=list[StockLevel], tags=["inventory"])
def stock_levels(db: DbSession):
    """Current stock of every active product, sorted by SKU."""
    return inventory_service.get_stock_levels(db)


@router.get("/inventory/low-stock", response_model=list[StockLevel], tags=["inventory"])
def low_stock(db: DbSession):
    """Active products whose stock is strictly below their minimum, sorted by SKU."""
    return inventory_service.get_low_stock(db)


@router.get("/inventory/summary", response_model=InventorySummary, tags=["inventory"])
def summary(db: DbSession):
    return inventory_service.get_summary(db)


@router.get(
    "/reports/inventory.csv",
    response_class=Response,
    tags=["reports"],
    responses={200: {"content": {"text/csv": {}}, "description": "Inventory as CSV file"}},
)
def inventory_csv(db: DbSession):
    """Download all active products as CSV (UTF-8 with BOM, so Excel shows umlauts)."""
    filename = f"inventory-{datetime.now(UTC):%Y-%m-%d}.csv"
    return Response(
        content="﻿" + inventory_service.export_inventory_csv(db),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

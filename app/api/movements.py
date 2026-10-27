"""HTTP routes for stock movements. Only request/response handling; rules live in the service."""

from fastapi import APIRouter, status

from app.api.params import Limit, Offset, ProductId
from app.database import DbSession
from app.errors import error_responses
from app.schemas import StockMovementCreate, StockMovementList, StockMovementRead
from app.services import stock as stock_service

router = APIRouter(prefix="/products", tags=["stock movements"])


@router.post(
    "/{product_id}/movements",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422),
)
def record_movement(product_id: ProductId, data: StockMovementCreate, db: DbSession):
    return stock_service.record_movement(db, product_id, data)


@router.get(
    "/{product_id}/movements",
    response_model=StockMovementList,
    responses=error_responses(404, 422),
)
def list_movements(product_id: ProductId, db: DbSession, limit: Limit = 20, offset: Offset = 0):
    """Movement history of one product, newest first. Works for inactive products too."""
    items, total = stock_service.list_movements(db, product_id, limit=limit, offset=offset)
    return StockMovementList(items=items, total=total, limit=limit, offset=offset)

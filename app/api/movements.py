"""HTTP routes for stock movements. Only request/response handling; rules live in the service."""

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas import StockMovementCreate, StockMovementRead
from app.services import stock as stock_service

router = APIRouter(prefix="/products", tags=["stock movements"])


@router.post(
    "/{product_id}/movements",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
)
def record_movement(product_id: int, data: StockMovementCreate, db: DbSession):
    return stock_service.record_movement(db, product_id, data)

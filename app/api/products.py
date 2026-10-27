"""HTTP routes for products. Only request/response handling; rules live in the service."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.params import Limit, Offset, ProductId
from app.database import DbSession
from app.errors import error_responses
from app.schemas import ProductCreate, ProductList, ProductRead, ProductUpdate
from app.services import products as product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422),
)
def create_product(data: ProductCreate, db: DbSession):
    return product_service.create_product(db, data)


@router.get("", response_model=ProductList, responses=error_responses(422))
def list_products(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Matches SKU or name")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
    include_inactive: bool = False,
):
    items, total = product_service.list_products(
        db, search=search, include_inactive=include_inactive, limit=limit, offset=offset
    )
    return ProductList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductRead, responses=error_responses(404, 422))
def get_product(product_id: ProductId, db: DbSession):
    return product_service.get_product(db, product_id)


@router.patch("/{product_id}", response_model=ProductRead, responses=error_responses(404, 409, 422))
def update_product(product_id: ProductId, data: ProductUpdate, db: DbSession):
    return product_service.update_product(db, product_id, data)


@router.post(
    "/{product_id}/deactivate",
    response_model=ProductRead,
    responses=error_responses(404, 422),
)
def deactivate_product(product_id: ProductId, db: DbSession):
    return product_service.deactivate_product(db, product_id)

"""HTTP routes for products. Only request/response handling; rules live in the service."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.database import DbSession
from app.schemas import ProductCreate, ProductList, ProductRead, ProductUpdate
from app.services import products as product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: DbSession):
    return product_service.create_product(db, data)


@router.get("", response_model=ProductList)
def list_products(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Matches SKU or name")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_inactive: bool = False,
):
    items, total = product_service.list_products(
        db, search=search, include_inactive=include_inactive, limit=limit, offset=offset
    )
    return ProductList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: DbSession):
    return product_service.get_product(db, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, data: ProductUpdate, db: DbSession):
    return product_service.update_product(db, product_id, data)


@router.post("/{product_id}/deactivate", response_model=ProductRead)
def deactivate_product(product_id: int, db: DbSession):
    return product_service.deactivate_product(db, product_id)

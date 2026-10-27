"""Pydantic schemas: the shape of data going into and out of the API.

They are deliberately separate from the ORM models in models.py. The API contract
(e.g. "clients may not send current_stock") is not the same as the database layout.
"""

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)

from app.models import MovementType

# SQLite stores integers as signed 64-bit values. Larger numbers from a client
# would crash the database driver, so every unbounded integer input uses this limit.
MAX_DB_INTEGER = 2**63 - 1


def _normalize_sku(value):
    # Runs before the pattern check (StringConstraints' to_upper would run too late).
    return value.strip().upper() if isinstance(value, str) else value


# SKUs are trimmed and upper-cased before validation, so " abc-1 " becomes "ABC-1".
Sku = Annotated[
    str,
    BeforeValidator(_normalize_sku),
    StringConstraints(min_length=1, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9._-]*$"),
]
ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=2000)]


class ProductCreate(BaseModel):
    # extra="forbid": unknown fields such as current_stock are rejected with 422.
    model_config = ConfigDict(extra="forbid")

    sku: Sku
    name: ProductName
    description: Description | None = None
    min_stock: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


class ProductUpdate(BaseModel):
    """Partial update: only the fields the client sends are changed.

    Stock is changed only through stock movements, so current_stock is not
    a field here. is_active is changed via the deactivate endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    sku: Sku | None = None
    name: ProductName | None = None
    description: Description | None = None
    min_stock: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)

    @field_validator("sku", "name", "min_stock")
    @classmethod
    def reject_explicit_null(cls, value):
        # Omitting a field is fine (validators don't run for defaults),
        # but sending null for a required column is not.
        if value is None:
            raise ValueError("may be omitted, but not set to null")
        return value


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    current_stock: int
    min_stock: int
    is_active: bool
    created_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class StockMovementCreate(BaseModel):
    """Quantity is always positive; the direction comes from movement_type."""

    model_config = ConfigDict(extra="forbid")

    movement_type: MovementType
    quantity: int = Field(gt=0, le=1_000_000)
    reason: Reason | None = None


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    movement_type: MovementType
    quantity: int
    reason: str | None
    created_at: datetime


class StockMovementList(BaseModel):
    items: list[StockMovementRead]
    total: int
    limit: int
    offset: int


class StockLevel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    current_stock: int
    min_stock: int

    @computed_field
    @property
    def is_low(self) -> bool:
        # Same rule as the low-stock query: strictly below the minimum.
        return self.current_stock < self.min_stock


class InventorySummary(BaseModel):
    """Totals over all active products."""

    active_products: int
    total_units: int
    low_stock_products: int
    out_of_stock_products: int

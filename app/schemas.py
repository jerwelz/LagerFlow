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
    field_validator,
)


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
    min_stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    """Partial update: only the fields the client sends are changed.

    Stock is changed only through stock movements, so current_stock is not
    a field here. is_active is changed via the deactivate endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    sku: Sku | None = None
    name: ProductName | None = None
    description: Description | None = None
    min_stock: int | None = Field(default=None, ge=0)

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

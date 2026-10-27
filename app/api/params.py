"""Path and query parameters shared by several routes."""

from typing import Annotated

from fastapi import Path, Query

from app.schemas import MAX_DB_INTEGER

ProductId = Annotated[int, Path(le=MAX_DB_INTEGER, description="Product ID")]
Limit = Annotated[int, Query(ge=1, le=100, description="Maximum number of items to return")]
Offset = Annotated[int, Query(ge=0, le=MAX_DB_INTEGER, description="Number of items to skip")]

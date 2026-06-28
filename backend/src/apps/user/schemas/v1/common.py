"""Common DTOs reused across the user API."""
from pydantic import BaseModel, Field


class PageMeta(BaseModel):
    """Pagination metadata embedded inside `data` for list endpoints."""

    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, ge=1, le=100)
    has_more: bool = False
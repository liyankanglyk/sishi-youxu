"""用户端 API 复用的通用 DTO。"""
from pydantic import BaseModel, Field


class PageMeta(BaseModel):
    """列表接口中嵌入 `data` 的分页元数据。"""

    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, ge=1, le=100)
    has_more: bool = False
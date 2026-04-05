"""
Shared response models used across all domains.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool = True
    data: Optional[Any] = None
    error: Optional[Dict[str, str]] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""

    success: bool = True
    data: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

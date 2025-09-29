"""
project/schemas/response.py - Standardized API responses
"""

from typing import Any, Dict, Optional, TypeVar, Generic
from pydantic import BaseModel
from datetime import datetime

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Universal API response wrapper"""

    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: str = datetime.utcnow().isoformat()


class ErrorDetail(BaseModel):
    """Error structure"""

    code: str
    message: str
    field: Optional[str] = None


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Success response builder"""
    response = {"success": True, "timestamp": datetime.utcnow().isoformat()}

    if data is not None:
        # Auto-serialize Pydantic models
        if isinstance(data, BaseModel):
            response["data"] = data.model_dump()
        elif (
            isinstance(data, list) and data and isinstance(data[0], BaseModel)
        ):
            response["data"] = [item.model_dump() for item in data]
        else:
            response["data"] = data

    if message:
        response["message"] = message
    if meta:
        response["meta"] = meta

    return response


def error_response(
    code: str,
    message: str,
    field: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Error response builder"""
    return {
        "success": False,
        "error": {"code": code, "message": message, "field": field},
        "meta": meta,
        "timestamp": datetime.utcnow().isoformat(),
    }


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: Optional[str] = None,
) -> Dict:
    """Paginated response builder"""
    return success_response(
        data=items,
        message=message,
        meta={
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        },
    )

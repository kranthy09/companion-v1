from typing import Any, Dict, List, Optional, TypeVar, Generic
from fastapi import HTTPException, status, Request
from pydantic import BaseModel
from functools import wraps
from fastapi import Response


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response"""

    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# Response utilities


def success_response(
    data: Any = None, message: str = None, request: Request = None
) -> dict:
    """Auto-serialize Pydantic models"""
    # Convert Pydantic model to dict
    if isinstance(data, BaseModel):
        data = data.model_dump()
    elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
        data = [item.model_dump() for item in data]

    return {
        "success": True,
        "data": data,
        "message": message,
        "request_id": (
            getattr(request.state, "request_id", None) if request else None
        ),
    }


def error_response(error: str, meta: Optional[Dict[str, Any]] = None) -> Dict:
    """Create a standardized error response"""
    response = {"success": False, "error": error}
    if meta:
        response["meta"] = meta
    return response


def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
    message: Optional[str] = None,
) -> Dict:
    """Create a standardized paginated response"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return success_response(
        data=items,
        message=message,
        meta={
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        },
    )


# Error raising helpers
def raise_not_found(resource: str, resource_id: Optional[Any] = None) -> None:
    """Raise a standardized not found error"""
    detail = f"{resource} not found"
    if resource_id is not None:
        detail = f"{resource} with id {resource_id} not found"
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def raise_bad_request(detail: str = "Bad request") -> None:
    """Raise a standardized bad request error"""
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def raise_unauthorized(detail: str = "Not authenticated") -> None:
    """Raise a standardized unauthorized error"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_forbidden(detail: str = "Not authorized") -> None:
    """Raise a standardized forbidden error"""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def api_response(func):
    """Decorator to standardize endpoint responses"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs) if callable(func) else func

        # If already a Response object, return as is
        if isinstance(result, Response):
            return result

        # If already formatted as our response, return as is
        if isinstance(result, dict) and "success" in result:
            return result

        # Wrap the result in our standard format
        return success_response(data=result)

    return wrapper

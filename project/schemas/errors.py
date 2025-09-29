"""
project/schemas/errors.py - Error code definitions
"""

from enum import Enum


class ErrorCode(str, Enum):
    # Authentication (AUTH_XXX)
    USER_NOT_FOUND = "AUTH_000"
    INVALID_CREDENTIALS = "AUTH_001"
    TOKEN_EXPIRED = "AUTH_002"
    TOKEN_INVALID = "AUTH_003"
    INSUFFICIENT_PERMISSIONS = "AUTH_004"
    ACCOUNT_INACTIVE = "AUTH_005"
    EMAIL_NOT_VERIFIED = "AUTH_006"
    TOKEN_REVOKED = "AUTH_007"

    # Authorization (AUTHZ_XXX)
    FORBIDDEN = "AUTHZ_001"
    RESOURCE_ACCESS_DENIED = "AUTHZ_002"

    # Notes (NOTE_XXX)
    NOTE_NOT_FOUND = "NOTE_001"
    NOTE_CREATE_FAILED = "NOTE_002"
    NOTE_UPDATE_FAILED = "NOTE_003"
    NOTE_DELETE_FAILED = "NOTE_004"

    # AI/Ollama (AI_XXX)
    OLLAMA_UNAVAILABLE = "AI_001"
    MODEL_BUSY = "AI_002"
    ENHANCEMENT_FAILED = "AI_003"
    INVALID_PROMPT = "AI_004"

    # Tasks (TASK_XXX)
    TASK_NOT_FOUND = "TASK_001"
    TASK_FAILED = "TASK_002"
    TASK_TIMEOUT = "TASK_003"

    # Validation (VAL_XXX)
    VALIDATION_ERROR = "VAL_001"
    INVALID_INPUT = "VAL_002"
    MISSING_FIELD = "VAL_003"

    # Rate Limiting (RATE_XXX)
    RATE_LIMIT_EXCEEDED = "RATE_001"
    THROTTLED = "RATE_002"

    # System (SYS_XXX)
    INTERNAL_ERROR = "SYS_001"
    DATABASE_ERROR = "SYS_002"
    SERVICE_UNAVAILABLE = "SYS_003"
    CSRF_VALIDATION_FAILED = "SYS_004"


# Error messages mapping
ERROR_MESSAGES = {
    ErrorCode.USER_NOT_FOUND: "User doesnot exists",
    ErrorCode.INVALID_CREDENTIALS: "Invalid email or password",
    ErrorCode.TOKEN_EXPIRED: "Token has expired",
    ErrorCode.TOKEN_INVALID: "Invalid token",
    ErrorCode.INSUFFICIENT_PERMISSIONS: "Insufficient permissions",
    ErrorCode.ACCOUNT_INACTIVE: "Account is inactive",
    ErrorCode.EMAIL_NOT_VERIFIED: "Email verification required",
    ErrorCode.TOKEN_REVOKED: "Token has been revoked",
    ErrorCode.FORBIDDEN: "Access forbidden",
    ErrorCode.NOTE_NOT_FOUND: "Note not found",
    ErrorCode.OLLAMA_UNAVAILABLE: "AI service unavailable",
    ErrorCode.TASK_NOT_FOUND: "Task not found",
    ErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
    ErrorCode.INTERNAL_ERROR: "Internal server error",
    ErrorCode.CSRF_VALIDATION_FAILED: "CSRF validation failed",
}

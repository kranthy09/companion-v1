"""
companion/project/auth/schemas.py

Updated Auth schemas for integer IDs
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Schema for creating a new user"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


class UserUpdate(BaseModel):
    """Schema for updating user data"""

    password: Optional[str] = Field(None, min_length=8, max_length=100)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserRead(BaseModel):
    """Schema for reading user data"""

    model_config = ConfigDict(from_attributes=True)

    id: int  # Changed from UUID to int
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserRead | None = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response schema"""

    access_token: str
    refresh_token: str  # ADD THIS
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """Authentication response schema"""

    user: UserRead
    token: Token

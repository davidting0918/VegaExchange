"""
Auth domain models — authentication requests and responses.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class GoogleAuthRequest(BaseModel):
    """Request body for Google authentication"""

    id_token: str


class AdminGoogleAuthRequest(BaseModel):
    """Request body for admin Google authentication"""

    id_token: str


class EmailRegisterRequest(BaseModel):
    """Request to register a new user with email/password"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=3, description="Password (minimum 3 characters)")
    user_name: Optional[str] = Field(None, description="Display name (optional, defaults to email username)")


class EmailLoginRequest(BaseModel):
    """Request to login with email/password"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

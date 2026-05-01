from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["ADMIN", "ANALYST", "VIEWER", "COMPANY_USER"]


class UserCreate(BaseModel):
    """Admin-invite payload."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: UserRole
    company_id: int | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: int | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

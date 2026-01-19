"""
User Schemas

Request and response schemas for user management endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.db.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a new user (admin use)."""

    password: str = Field(..., min_length=8)
    role: UserRole = Field(default=UserRole.VIEWER)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)


class UserUpdate(BaseModel):
    """Schema for updating user (self-update)."""

    username: str | None = Field(None, min_length=3, max_length=50)


class UserAdminUpdate(BaseModel):
    """Schema for admin updating any user."""

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    role: UserRole | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class UserResponse(BaseModel):
    """User response schema."""

    id: UUID
    email: str
    username: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    """Detailed user response with additional info."""

    updated_at: datetime
    failed_login_attempts: int
    is_locked: bool


class UserListResponse(BaseModel):
    """Paginated list of users."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserStatsResponse(BaseModel):
    """User statistics for admin dashboard."""

    total_users: int
    active_users: int
    verified_users: int
    users_by_role: dict[str, int]
    recent_registrations: int  # Last 7 days
    recent_logins: int  # Last 24 hours

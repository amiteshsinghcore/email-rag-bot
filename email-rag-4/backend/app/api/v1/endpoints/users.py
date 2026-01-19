"""
User Management Endpoints

CRUD operations for user management.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import ActiveUser, AdminUser, DbSession
from app.db.models.user import UserRole
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    UserAdminUpdate,
    UserCreate,
    UserDetailResponse,
    UserListResponse,
    UserResponse,
    UserStatsResponse,
    UserUpdate,
)
from app.services.user_service import get_user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserDetailResponse)
async def get_current_user(current_user: ActiveUser) -> UserDetailResponse:
    """Get current user's detailed information."""
    return UserDetailResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login_at=current_user.last_login_at,
        failed_login_attempts=current_user.failed_login_attempts,
        is_locked=current_user.is_locked,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    data: UserUpdate,
    current_user: ActiveUser,
    db: DbSession,
) -> UserResponse:
    """Update current user's profile."""
    service = get_user_service(db)

    try:
        user = await service.update_user(current_user, data)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ===========================================
# Admin Endpoints
# ===========================================


@router.get("", response_model=UserListResponse)
async def list_users(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    role: UserRole | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by email or username"),
) -> UserListResponse:
    """List all users (admin only)."""
    service = get_user_service(db)
    users, total = await service.list_users(
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
        search=search,
    )

    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(admin: AdminUser, db: DbSession) -> UserStatsResponse:
    """Get user statistics (admin only)."""
    service = get_user_service(db)
    return await service.get_stats()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    admin: AdminUser,
    db: DbSession,
) -> UserResponse:
    """Create a new user (admin only)."""
    service = get_user_service(db)

    try:
        user = await service.create_user(data)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: UUID,
    admin: AdminUser,
    db: DbSession,
) -> UserDetailResponse:
    """Get user by ID (admin only)."""
    service = get_user_service(db)
    user = await service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        failed_login_attempts=user.failed_login_attempts,
        is_locked=user.is_locked,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserAdminUpdate,
    admin: AdminUser,
    db: DbSession,
) -> UserResponse:
    """Update user by ID (admin only)."""
    service = get_user_service(db)
    user = await service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        updated_user = await service.admin_update_user(user, data)
        return UserResponse.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: UUID,
    admin: AdminUser,
    db: DbSession,
    hard_delete: bool = Query(False, description="Permanently delete user"),
) -> MessageResponse:
    """Delete user by ID (admin only)."""
    service = get_user_service(db)
    user = await service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deletion
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    await service.delete_user(user, hard_delete=hard_delete)

    action = "permanently deleted" if hard_delete else "deleted"
    return MessageResponse(message=f"User {action} successfully")


@router.post("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    user_id: UUID,
    admin: AdminUser,
    db: DbSession,
) -> UserResponse:
    """Unlock a locked user account (admin only)."""
    service = get_user_service(db)
    user = await service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not locked",
        )

    updated_user = await service.unlock_user(user)
    return UserResponse.model_validate(updated_user)


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_user_password(
    user_id: UUID,
    new_password: str,
    admin: AdminUser,
    db: DbSession,
) -> MessageResponse:
    """Reset user's password (admin only)."""
    service = get_user_service(db)
    user = await service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await service.reset_password(user, new_password)
    return MessageResponse(message="Password reset successfully")

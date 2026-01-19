"""
User Service

Business logic for user management operations.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.models.user import User, UserRole
from app.schemas.user import UserAdminUpdate, UserCreate, UserStatsResponse, UserUpdate


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """
        List users with pagination and filtering.

        Returns:
            Tuple of (users list, total count)
        """
        query = select(User).where(User.deleted_at.is_(None))

        # Apply filters
        if role is not None:
            query = query.where(User.role == role)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (User.email.ilike(search_pattern)) | (User.username.ilike(search_pattern))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def create_user(self, data: UserCreate) -> User:
        """Create a new user (admin use)."""
        # Check for existing email
        existing = await self.get_by_email(data.email)
        if existing:
            raise ValueError("Email already registered")

        # Check for existing username
        existing = await self.get_by_username(data.username)
        if existing:
            raise ValueError("Username already taken")

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=get_password_hash(data.password),
            role=data.role,
            is_active=data.is_active,
            is_verified=data.is_verified,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User created by admin: {user.email}")
        return user

    async def update_user(self, user: User, data: UserUpdate) -> User:
        """Update user's own profile."""
        if data.username is not None:
            # Check username availability
            existing = await self.get_by_username(data.username)
            if existing and existing.id != user.id:
                raise ValueError("Username already taken")
            user.username = data.username

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User updated their profile: {user.email}")
        return user

    async def admin_update_user(self, user: User, data: UserAdminUpdate) -> User:
        """Admin update any user."""
        if data.email is not None:
            existing = await self.get_by_email(data.email)
            if existing and existing.id != user.id:
                raise ValueError("Email already registered")
            user.email = data.email

        if data.username is not None:
            existing = await self.get_by_username(data.username)
            if existing and existing.id != user.id:
                raise ValueError("Username already taken")
            user.username = data.username

        if data.role is not None:
            user.role = data.role

        if data.is_active is not None:
            user.is_active = data.is_active

        if data.is_verified is not None:
            user.is_verified = data.is_verified

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"Admin updated user: {user.email}")
        return user

    async def delete_user(self, user: User, hard_delete: bool = False) -> None:
        """
        Delete a user.

        Args:
            user: User to delete
            hard_delete: If True, permanently delete. If False, soft delete.
        """
        if hard_delete:
            await self.db.delete(user)
            logger.warning(f"User permanently deleted: {user.email}")
        else:
            user.deleted_at = datetime.now(timezone.utc)
            user.is_active = False
            logger.info(f"User soft deleted: {user.email}")

        await self.db.commit()

    async def unlock_user(self, user: User) -> User:
        """Unlock a locked user account."""
        user.locked_until = None
        user.failed_login_attempts = 0
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User account unlocked: {user.email}")
        return user

    async def reset_password(self, user: User, new_password: str) -> User:
        """Reset user's password (admin use)."""
        user.hashed_password = get_password_hash(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"Password reset for user: {user.email}")
        return user

    async def get_stats(self) -> UserStatsResponse:
        """Get user statistics for admin dashboard."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        day_ago = now - timedelta(days=1)

        # Total users (not deleted)
        total = await self.db.scalar(
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        )

        # Active users
        active = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.is_active.is_(True))
        )

        # Verified users
        verified = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.is_verified.is_(True))
        )

        # Users by role
        role_counts = {}
        for role in UserRole:
            count = await self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), User.role == role)
            )
            role_counts[role.value] = count or 0

        # Recent registrations (last 7 days)
        recent_regs = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.created_at >= week_ago)
        )

        # Recent logins (last 24 hours)
        recent_logins = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.deleted_at.is_(None),
                User.last_login_at.isnot(None),
                User.last_login_at >= day_ago,
            )
        )

        return UserStatsResponse(
            total_users=total or 0,
            active_users=active or 0,
            verified_users=verified or 0,
            users_by_role=role_counts,
            recent_registrations=recent_regs or 0,
            recent_logins=recent_logins or 0,
        )


def get_user_service(db: AsyncSession) -> UserService:
    """Factory function to create UserService."""
    return UserService(db)

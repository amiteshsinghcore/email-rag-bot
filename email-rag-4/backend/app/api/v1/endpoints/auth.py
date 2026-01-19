"""
Authentication Endpoints

Handles user login, registration, token refresh, and password management.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from sqlalchemy import select

from app.api.deps import ActiveUser, DbSession
from app.core.security import (
    create_token_pair,
    get_password_hash,
    verify_password,
    verify_refresh_token,
)
from app.db.models.user import User, UserRole
from app.schemas.auth import (
    AuthenticatedUser,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_role_value(role: str | UserRole) -> str:
    """Get role string value from either string or UserRole enum."""
    return role.value if isinstance(role, UserRole) else role


def user_to_authenticated(user: User) -> AuthenticatedUser:
    """Convert User model to AuthenticatedUser schema."""
    return AuthenticatedUser(
        id=str(user.id),
        email=user.email,
        username=user.username,
        role=get_role_value(user.role),
        is_verified=user.is_verified,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: DbSession) -> RegisterResponse:
    """
    Register a new user account.

    - Creates user with default VIEWER role
    - Returns tokens immediately (email verification can be added later)
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if username already exists
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user
    user = User(
        email=request.email,
        username=request.username,
        hashed_password=get_password_hash(request.password),
        role=UserRole.VIEWER.value,
        is_active=True,
        is_verified=False,  # Would be True after email verification
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user registered: {user.email}")

    # Generate tokens
    tokens = create_token_pair(str(user.id), get_role_value(user.role))

    return RegisterResponse(
        message="Registration successful",
        user=user_to_authenticated(user),
        tokens=TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        ),
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: DbSession) -> LoginResponse:
    """
    Authenticate user and return tokens.

    - Validates credentials
    - Checks account status (active, not locked)
    - Updates login timestamp
    - Returns access and refresh tokens
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Account locking disabled by user request
    # if user.is_locked:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Account is locked due to too many failed attempts",
    #     )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        # We no longer lock accounts
        # user.failed_login_attempts += 1
        # if user.failed_login_attempts >= 5: ...
        # await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Successful login - reset failed attempts just in case
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(f"User logged in: {user.email}")

    # Generate tokens
    tokens = create_token_pair(str(user.id), get_role_value(user.role))

    return LoginResponse(
        user=user_to_authenticated(user),
        tokens=TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    """
    Refresh access token using refresh token.

    - Validates refresh token
    - Issues new access and refresh tokens
    """
    payload = verify_refresh_token(request.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Generate new token pair
    tokens = create_token_pair(str(user.id), get_role_value(user.role))

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: ActiveUser) -> MessageResponse:
    """
    Logout current user.

    Note: With JWT, logout is primarily client-side (discard tokens).
    This endpoint can be used for audit logging or token blacklisting.
    """
    logger.info(f"User logged out: {current_user.email}")

    # In a production system, you might:
    # - Add the token to a blacklist in Redis
    # - Clear any server-side sessions
    # - Log the logout event for audit

    return MessageResponse(message="Logged out successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: ActiveUser,
    db: DbSession,
) -> MessageResponse:
    """
    Change current user's password.

    - Verifies current password
    - Updates to new password
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    logger.info(f"Password changed for user: {current_user.email}")

    return MessageResponse(message="Password changed successfully")


@router.get("/me", response_model=AuthenticatedUser)
async def get_current_user_info(current_user: ActiveUser) -> AuthenticatedUser:
    """Get current authenticated user's information."""
    return user_to_authenticated(current_user)

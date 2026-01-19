"""
Security Module

Provides JWT token management, password hashing, and authentication utilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings


# Password hashing context using bcrypt
# Set truncate_error=False to silently truncate passwords over 72 bytes
# This prevents issues with bcrypt's 72-byte limit in newer versions
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    sub: str  # Subject (user ID)
    exp: datetime  # Expiration time
    iat: datetime  # Issued at time
    type: str  # Token type (access, refresh)
    role: str | None = None  # User role for quick access


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiration in seconds


# ===========================================
# Password Utilities
# ===========================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The bcrypt hash of the password
    """
    return pwd_context.hash(password)


# ===========================================
# JWT Token Utilities
# ===========================================


def create_access_token(
    subject: str,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject (usually user ID)
        role: Optional user role to include in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT access token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    now = datetime.now(timezone.utc)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "access",
    }

    if role:
        to_encode["role"] = role

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The subject (usually user ID)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    now = datetime.now(timezone.utc)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(subject: str, role: str | None = None) -> TokenPair:
    """
    Create both access and refresh tokens.

    Args:
        subject: The subject (usually user ID)
        role: Optional user role to include in access token

    Returns:
        TokenPair with both tokens
    """
    access_token = create_access_token(subject, role)
    refresh_token = create_refresh_token(subject)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def decode_token(token: str) -> TokenPayload | None:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        TokenPayload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            type=payload["type"],
            role=payload.get("role"),
        )
    except JWTError:
        return None


def verify_access_token(token: str) -> TokenPayload | None:
    """
    Verify an access token is valid and not expired.

    Args:
        token: The JWT access token to verify

    Returns:
        TokenPayload if valid access token, None otherwise
    """
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.type != "access":
        return None

    if payload.exp < datetime.now(timezone.utc):
        return None

    return payload


def verify_refresh_token(token: str) -> TokenPayload | None:
    """
    Verify a refresh token is valid and not expired.

    Args:
        token: The JWT refresh token to verify

    Returns:
        TokenPayload if valid refresh token, None otherwise
    """
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.type != "refresh":
        return None

    if payload.exp < datetime.now(timezone.utc):
        return None

    return payload


# ===========================================
# Password Validation
# ===========================================


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password meets security requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        errors.append("Password must contain at least one special character")

    return len(errors) == 0, errors

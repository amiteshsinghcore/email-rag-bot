"""
Tests for Authentication API Endpoints

Tests for login, registration, token refresh, and password management.

Note: These tests require PostgreSQL database due to PostgreSQL-specific types
in the database models (ARRAY, TSVECTOR). They are skipped when PostgreSQL
is not available.
"""

import pytest
from httpx import AsyncClient

from app.core.security import verify_password

# Skip all tests in this module - requires PostgreSQL
pytestmark = pytest.mark.skip(reason="Requires PostgreSQL database (models use ARRAY/TSVECTOR types)")


# ===========================================
# Registration Tests
# ===========================================

class TestRegistration:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Registration successful"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["username"] == "newuser"
        assert data["user"]["role"] == "viewer"
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, client: AsyncClient, test_user_data: dict
    ):
        """Test registration fails with duplicate email."""
        # First registration
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "user1",
                "password": "SecurePass123!",
            },
        )

        # Second registration with same email
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "user2",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Test registration fails with duplicate username."""
        # First registration
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user1@example.com",
                "username": "sameusername",
                "password": "SecurePass123!",
            },
        )

        # Second registration with same username
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user2@example.com",
                "username": "sameusername",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration fails with invalid email format."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "username": "validuser",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration fails with missing required fields."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                # Missing username and password
            },
        )

        assert response.status_code == 422


# ===========================================
# Login Tests
# ===========================================

class TestLogin:
    """Tests for user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, client: AsyncClient, test_user, test_user_data: dict
    ):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == test_user_data["email"]
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, client: AsyncClient, test_user, test_user_data: dict
    ):
        """Test login fails with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login fails for non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword123!",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, client: AsyncClient, test_user, test_user_data: dict, db_session
    ):
        """Test login fails for inactive user."""
        # Deactivate user
        test_user.is_active = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()


# ===========================================
# Token Refresh Tests
# ===========================================

class TestTokenRefresh:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_success(
        self, client: AsyncClient, test_user, test_user_data: dict
    ):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        refresh_token = login_response.json()["tokens"]["refresh_token"]

        # Refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New tokens should be different
        assert data["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh fails with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(
        self, client: AsyncClient, test_user, test_user_data: dict
    ):
        """Test refresh fails when using access token instead of refresh token."""
        # Login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        access_token = login_response.json()["tokens"]["access_token"]

        # Try to use access token as refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401


# ===========================================
# Logout Tests
# ===========================================

class TestLogout:
    """Tests for logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, authenticated_client: AsyncClient):
        """Test successful logout."""
        response = await authenticated_client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_unauthenticated(self, client: AsyncClient):
        """Test logout fails without authentication."""
        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 401


# ===========================================
# Change Password Tests
# ===========================================

class TestChangePassword:
    """Tests for change password endpoint."""

    @pytest.mark.asyncio
    async def test_change_password_success(
        self,
        authenticated_client: AsyncClient,
        test_user,
        test_user_data: dict,
        db_session,
    ):
        """Test successful password change."""
        response = await authenticated_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": test_user_data["password"],
                "new_password": "NewSecurePass456!",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"

        # Verify password was actually changed
        await db_session.refresh(test_user)
        assert verify_password("NewSecurePass456!", test_user.hashed_password)

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, authenticated_client: AsyncClient
    ):
        """Test password change fails with wrong current password."""
        response = await authenticated_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongCurrentPass123!",
                "new_password": "NewSecurePass456!",
            },
        )

        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(self, client: AsyncClient):
        """Test password change requires authentication."""
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
            },
        )

        assert response.status_code == 401


# ===========================================
# Get Current User Tests
# ===========================================

class TestGetCurrentUser:
    """Tests for get current user endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_success(
        self, authenticated_client: AsyncClient, test_user_data: dict
    ):
        """Test getting current user info."""
        response = await authenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["username"] == test_user_data["username"]

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Test get current user fails without authentication."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

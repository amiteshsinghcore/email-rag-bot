"""
Tests for Security Module

Tests for password hashing, JWT token management, and authentication utilities.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    get_password_hash,
    validate_password_strength,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)


# ===========================================
# Password Hashing Tests
# ===========================================

class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password(self):
        """Test password hashing produces valid bcrypt hash."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt identifier
        assert len(hashed) == 60  # bcrypt hash length

    def test_verify_password_correct(self):
        """Test verifying correct password returns True."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password returns False."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salting)."""
        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        # Both should still verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


# ===========================================
# Password Validation Tests
# ===========================================

class TestPasswordValidation:
    """Tests for password strength validation."""

    def test_valid_password(self):
        """Test valid password passes validation."""
        password = "ValidPass123!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is True
        assert len(errors) == 0

    def test_password_too_short(self):
        """Test password under 8 characters fails."""
        password = "Pass1!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert any("8 characters" in error for error in errors)

    def test_password_missing_uppercase(self):
        """Test password without uppercase fails."""
        password = "validpass123!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert any("uppercase" in error for error in errors)

    def test_password_missing_lowercase(self):
        """Test password without lowercase fails."""
        password = "VALIDPASS123!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert any("lowercase" in error for error in errors)

    def test_password_missing_digit(self):
        """Test password without digit fails."""
        password = "ValidPassword!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert any("digit" in error for error in errors)

    def test_password_missing_special(self):
        """Test password without special character fails."""
        password = "ValidPass123"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert any("special" in error for error in errors)

    def test_password_multiple_failures(self):
        """Test password with multiple issues returns all errors."""
        password = "weak"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert len(errors) >= 3  # Short, no uppercase, no digit, no special


# ===========================================
# JWT Token Tests
# ===========================================

class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_access_token(self):
        """Test access token creation."""
        subject = "user-123"
        token = create_access_token(subject)

        assert token is not None
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_create_access_token_with_role(self):
        """Test access token creation with role."""
        subject = "user-123"
        role = "admin"
        token = create_access_token(subject, role=role)

        payload = decode_token(token)
        assert payload is not None
        assert payload.role == role

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        subject = "user-123"
        token = create_refresh_token(subject)

        assert token is not None
        assert len(token) > 0

    def test_create_token_pair(self):
        """Test token pair creation."""
        subject = "user-123"
        role = "investigator"
        pair = create_token_pair(subject, role)

        assert pair.access_token is not None
        assert pair.refresh_token is not None
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

    def test_decode_access_token(self):
        """Test decoding valid access token."""
        subject = "user-123"
        token = create_access_token(subject)

        payload = decode_token(token)

        assert payload is not None
        assert payload.sub == subject
        assert payload.type == "access"
        assert payload.exp > datetime.now(timezone.utc)

    def test_decode_refresh_token(self):
        """Test decoding valid refresh token."""
        subject = "user-123"
        token = create_refresh_token(subject)

        payload = decode_token(token)

        assert payload is not None
        assert payload.sub == subject
        assert payload.type == "refresh"

    def test_decode_invalid_token(self):
        """Test decoding invalid token returns None."""
        invalid_token = "not.a.valid.token"

        payload = decode_token(invalid_token)

        assert payload is None

    def test_verify_access_token_valid(self):
        """Test verifying valid access token."""
        subject = "user-123"
        token = create_access_token(subject)

        payload = verify_access_token(token)

        assert payload is not None
        assert payload.sub == subject

    def test_verify_access_token_with_refresh_token(self):
        """Test verifying access token fails for refresh token."""
        subject = "user-123"
        refresh_token = create_refresh_token(subject)

        payload = verify_access_token(refresh_token)

        assert payload is None  # Should fail - wrong token type

    def test_verify_refresh_token_valid(self):
        """Test verifying valid refresh token."""
        subject = "user-123"
        token = create_refresh_token(subject)

        payload = verify_refresh_token(token)

        assert payload is not None
        assert payload.sub == subject

    def test_verify_refresh_token_with_access_token(self):
        """Test verifying refresh token fails for access token."""
        subject = "user-123"
        access_token = create_access_token(subject)

        payload = verify_refresh_token(access_token)

        assert payload is None  # Should fail - wrong token type

    def test_custom_expiration(self):
        """Test token with custom expiration time."""
        subject = "user-123"
        expires_delta = timedelta(hours=2)
        token = create_access_token(subject, expires_delta=expires_delta)

        payload = decode_token(token)

        assert payload is not None
        # Expiration should be approximately 2 hours from now
        expected_exp = datetime.now(timezone.utc) + timedelta(hours=2)
        assert abs((payload.exp - expected_exp).total_seconds()) < 10

    def test_expired_token(self):
        """Test expired token verification fails."""
        subject = "user-123"
        # Create token that expired 1 hour ago
        expires_delta = timedelta(hours=-1)
        token = create_access_token(subject, expires_delta=expires_delta)

        payload = verify_access_token(token)

        assert payload is None  # Should fail - expired


# ===========================================
# Edge Cases
# ===========================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_password_hash(self):
        """Test hashing empty password still works."""
        password = ""
        hashed = get_password_hash(password)

        assert hashed is not None
        assert verify_password(password, hashed) is True

    def test_unicode_password(self):
        """Test password with unicode characters."""
        password = "Válid🔐Pass123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_long_password(self):
        """Test very long password."""
        # bcrypt has a 72-byte limit, but it should handle gracefully
        password = "A" * 100 + "a1!"
        hashed = get_password_hash(password)

        # Should at least hash without error
        assert hashed is not None

    def test_uuid_subject(self):
        """Test token with UUID subject."""
        from uuid import uuid4
        subject = str(uuid4())
        token = create_access_token(subject)

        payload = decode_token(token)

        assert payload is not None
        assert payload.sub == subject

    def test_token_payload_timestamps(self):
        """Test token contains proper timestamps."""
        subject = "user-123"
        # JWT tokens truncate to seconds, so we need to compare without microseconds
        before = datetime.now(timezone.utc).replace(microsecond=0)
        token = create_access_token(subject)
        after = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=1)

        payload = decode_token(token)

        assert payload is not None
        # iat is truncated to seconds in JWT, so compare accordingly
        assert before <= payload.iat <= after
        assert payload.exp > payload.iat

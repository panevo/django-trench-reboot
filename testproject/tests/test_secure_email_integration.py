"""
Integration tests for secure email MFA authentication flow.

These tests verify that the secure_email backend works correctly in the
full authentication flow, from login to second factor verification.
"""

import pytest
import re

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import patch

from trench.command.create_secret import create_secret_command
from trench.models import MFAMethod
from trench.utils import user_token_generator


User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client."""
    return APIClient()


@pytest.fixture
def user_with_secure_email_mfa():
    """Create a user with secure_email MFA enabled."""
    user, created = User.objects.get_or_create(
        username="mfa_user",
        email="mfa@test.com",
    )
    if created:
        user.set_password("password123")
        user.is_active = True
        user.save()

    # Create secure_email MFA method
    mfa_method, _ = MFAMethod.objects.get_or_create(
        user=user,
        name="secure_email",
        defaults={
            "secret": create_secret_command(),
            "is_primary": True,
            "is_active": True,
        },
    )
    return user


@pytest.mark.django_db
class TestSecureEmailIntegration:
    """Integration tests for secure email MFA"""

    def test_full_login_flow_with_secure_email(
        self, api_client, user_with_secure_email_mfa
    ):
        """Test complete login flow with secure email MFA."""
        user = user_with_secure_email_mfa

        # Mock email sending
        with patch("trench.backends.secure_mail.send_mail") as mock_send:
            # Step 1: First factor authentication (username/password)
            # Note: We'd need the actual login endpoint here - for now test the backend directly
            from trench.backends.secure_mail import SecureMailMessageDispatcher
            from trench.settings import trench_settings

            mfa_method = user.mfa_methods.get(name="secure_email")
            config = trench_settings.MFA_METHODS["secure_email"]

            dispatcher = SecureMailMessageDispatcher(
                mfa_method=mfa_method, config=config
            )
            response = dispatcher.dispatch_message()

            # Verify email was sent
            assert mock_send.called
            assert response.status_code == 200

            # Extract code from email
            call_kwargs = mock_send.call_args[1]
            message = call_kwargs["message"]
            code = re.findall(r"\b\d{6}\b", message)[0]

        # Step 2: Second factor authentication (code validation)
        assert dispatcher.validate_code(code) is True

        # Step 3: Try to use the code again (should fail - single use)
        assert dispatcher.validate_code(code) is False

    def test_expired_code_flow(self, api_client, user_with_secure_email_mfa):
        """Test that expired codes are rejected."""
        user = user_with_secure_email_mfa

        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.settings import trench_settings
        from django.utils import timezone
        from datetime import timedelta

        mfa_method = user.mfa_methods.get(name="secure_email")
        config = trench_settings.MFA_METHODS["secure_email"]

        # Generate code
        with patch("trench.backends.secure_mail.send_mail") as mock_send:
            dispatcher = SecureMailMessageDispatcher(
                mfa_method=mfa_method, config=config
            )
            dispatcher.dispatch_message()

            # Extract code
            call_kwargs = mock_send.call_args[1]
            message = call_kwargs["message"]
            code = re.findall(r"\b\d{6}\b", message)[0]

        # Manually expire the token
        mfa_method.refresh_from_db()
        mfa_method.token_expires_at = timezone.now() - timedelta(seconds=1)
        mfa_method.save()

        # Code should be rejected
        assert dispatcher.validate_code(code) is False

        # Token should be cleared
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is None

    def test_brute_force_protection(self, api_client, user_with_secure_email_mfa):
        """Test that too many failed attempts lock the token."""
        user = user_with_secure_email_mfa

        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.settings import trench_settings

        mfa_method = user.mfa_methods.get(name="secure_email")
        config = trench_settings.MFA_METHODS["secure_email"]

        # Generate code
        with patch("trench.backends.secure_mail.send_mail"):
            dispatcher = SecureMailMessageDispatcher(
                mfa_method=mfa_method, config=config
            )
            dispatcher.dispatch_message()

        # Try wrong code 5 times (should lock after 5 failures)
        for i in range(5):
            result = dispatcher.validate_code("000000")
            assert result is False
            mfa_method.refresh_from_db()
            assert mfa_method.token_failures == i + 1

        # Token should still exist after 5 failures
        assert mfa_method.token_hash is not None

        # Next attempt should lock the token
        result = dispatcher.validate_code("000000")
        assert result is False

        # Token should be cleared
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is None
        assert mfa_method.token_failures == 0

    def test_resend_code_invalidates_old(self, api_client, user_with_secure_email_mfa):
        """Test that requesting a new code invalidates the old one."""
        user = user_with_secure_email_mfa

        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.settings import trench_settings

        mfa_method = user.mfa_methods.get(name="secure_email")
        config = trench_settings.MFA_METHODS["secure_email"]

        # Generate first code
        with patch("trench.backends.secure_mail.send_mail") as mock_send:
            dispatcher = SecureMailMessageDispatcher(
                mfa_method=mfa_method, config=config
            )
            dispatcher.dispatch_message()

            call_kwargs = mock_send.call_args[1]
            message1 = call_kwargs["message"]
            code1 = re.findall(r"\b\d{6}\b", message1)[0]

        # Generate second code
        with patch("trench.backends.secure_mail.send_mail") as mock_send:
            dispatcher.dispatch_message()

            call_kwargs = mock_send.call_args[1]
            message2 = call_kwargs["message"]
            code2 = re.findall(r"\b\d{6}\b", message2)[0]

        # First code should no longer work
        assert dispatcher.validate_code(code1) is False

        # Second code should work
        assert dispatcher.validate_code(code2) is True

    def test_comparison_with_basic_email_backend(
        self, api_client, user_with_secure_email_mfa
    ):
        """
        Test that demonstrates the difference between basic_email and secure_email.

        The basic_email backend uses TOTP which generates the same code for
        multiple requests within a time window. The secure_email backend
        generates a new random code each time.
        """
        user = user_with_secure_email_mfa

        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.backends.basic_mail import SendMailMessageDispatcher
        from trench.settings import trench_settings

        # Test secure_email - should generate different codes
        mfa_method = user.mfa_methods.get(name="secure_email")
        config = trench_settings.MFA_METHODS["secure_email"]

        codes = []
        for _ in range(3):
            with patch("trench.backends.secure_mail.send_mail") as mock_send:
                dispatcher = SecureMailMessageDispatcher(
                    mfa_method=mfa_method, config=config
                )
                dispatcher.dispatch_message()

                call_kwargs = mock_send.call_args[1]
                message = call_kwargs["message"]
                code = re.findall(r"\b\d{6}\b", message)[0]
                codes.append(code)

        # All codes should be different (with very high probability)
        assert len(set(codes)) == 3

        # Test basic_email - would generate the same code within time window
        # (We won't actually test this as it requires changing the MFA method,
        # but the difference is documented in the secure_email backend)

    def test_secure_storage_of_token(self, api_client, user_with_secure_email_mfa):
        """Verify that tokens are stored as hashes, not plaintext."""
        user = user_with_secure_email_mfa

        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.settings import trench_settings

        mfa_method = user.mfa_methods.get(name="secure_email")
        config = trench_settings.MFA_METHODS["secure_email"]

        # Generate code
        with patch("trench.backends.secure_mail.send_mail") as mock_send:
            dispatcher = SecureMailMessageDispatcher(
                mfa_method=mfa_method, config=config
            )
            dispatcher.dispatch_message()

            # Extract code from email
            call_kwargs = mock_send.call_args[1]
            message = call_kwargs["message"]
            code = re.findall(r"\b\d{6}\b", message)[0]

        # Check database
        mfa_method.refresh_from_db()

        # The stored hash should not equal the plaintext code
        assert mfa_method.token_hash != code

        # The hash should be 64 characters (SHA-256 in hex)
        assert len(mfa_method.token_hash) == 64
        assert all(c in "0123456789abcdef" for c in mfa_method.token_hash)

        # Should not be able to reverse the hash
        # (This is inherent to SHA-256, but we verify the length/format)

    def test_salt_prevents_rainbow_table_attacks(self, api_client):
        """
        Verify that using salt prevents rainbow table attacks.

        Without salt, an attacker with database access could pre-compute hashes
        for all 1 million possible 6-digit codes and reverse any hash instantly.
        With salt (using the MFA method's secret), each user requires a separate
        rainbow table, making the attack infeasible.
        """
        from trench.backends.secure_mail import SecureMailMessageDispatcher
        from trench.settings import trench_settings
        from trench.command.create_secret import create_secret_command

        # Create two users with different secrets
        user1, _ = User.objects.get_or_create(
            username="salt_test_user1",
            email="salt1@test.com",
        )
        user2, _ = User.objects.get_or_create(
            username="salt_test_user2",
            email="salt2@test.com",
        )

        # Create MFA methods with different secrets (salts)
        mfa1, _ = MFAMethod.objects.get_or_create(
            user=user1,
            name="secure_email",
            defaults={
                "secret": create_secret_command(),
                "is_primary": True,
                "is_active": True,
            },
        )

        mfa2, _ = MFAMethod.objects.get_or_create(
            user=user2,
            name="secure_email",
            defaults={
                "secret": create_secret_command(),
                "is_primary": True,
                "is_active": True,
            },
        )

        # Verify secrets are different
        assert mfa1.secret != mfa2.secret

        config = trench_settings.MFA_METHODS["secure_email"]

        # Force both users to get the same code by mocking _generate_code
        test_code = "424242"

        with patch("trench.backends.secure_mail.send_mail"):
            dispatcher1 = SecureMailMessageDispatcher(mfa_method=mfa1, config=config)
            with patch.object(dispatcher1, "_generate_code", return_value=test_code):
                dispatcher1.dispatch_message()

            dispatcher2 = SecureMailMessageDispatcher(mfa_method=mfa2, config=config)
            with patch.object(dispatcher2, "_generate_code", return_value=test_code):
                dispatcher2.dispatch_message()

        # Refresh from database
        mfa1.refresh_from_db()
        mfa2.refresh_from_db()

        # CRITICAL SECURITY TEST: Same code MUST produce different hashes
        # This is the key defense against rainbow table attacks
        assert (
            mfa1.token_hash != mfa2.token_hash
        ), "Salt MUST make identical codes hash differently for different users!"

        # Verify validation still works correctly for each user
        assert dispatcher1.validate_code(test_code) is True
        assert dispatcher2.validate_code(test_code) is True

        # This proves:
        # 1. Same code + different salt = different hash (rainbow table protection)
        # 2. Each user's hash can only be validated with their own salt
        # 3. An attacker would need 1M * N rainbow tables (N = number of users)

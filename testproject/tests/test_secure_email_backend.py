"""
Tests for the SecureMailMessageDispatcher backend.

This backend generates single-use random codes for email MFA,
unlike the basic email backend which uses TOTP codes.
"""
import pytest
import time

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

from trench.backends.secure_mail import SecureMailMessageDispatcher
from trench.command.create_secret import create_secret_command
from trench.models import MFAMethod


User = get_user_model()


@pytest.fixture
def user_with_secure_email():
    """Create a user with secure email MFA method."""
    user, created = User.objects.get_or_create(
        username="secure_test_user",
        email="secure@test.com",
    )
    if created:
        user.set_password("testpassword")
        user.is_active = True
        user.save()
    
    # Create secure_email MFA method
    mfa_method, _ = MFAMethod.objects.get_or_create(
        user=user,
        name="secure_email",
        defaults={
            'secret': create_secret_command(),
            'is_primary': True,
            'is_active': True,
        }
    )
    return user, mfa_method


@pytest.mark.django_db
class TestSecureEmailBackend:
    """Tests for SecureMailMessageDispatcher"""
    
    def test_dispatch_generates_and_stores_code(self, user_with_secure_email, settings):
        """Test that dispatch_message generates a code and stores its hash."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Mock send_mail to avoid actually sending emails
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            response = dispatcher.dispatch_message()
        
        # Check response
        assert response.status_code == 200
        assert 'Email message with MFA code has been sent' in str(response.data.get('details'))
        
        # Refresh from DB
        mfa_method.refresh_from_db()
        
        # Check that hash was stored
        assert mfa_method.token_hash is not None
        assert len(mfa_method.token_hash) == 64  # SHA-256 hex is 64 chars
        
        # Check that expiration was set
        assert mfa_method.token_expires_at is not None
        assert mfa_method.token_expires_at > timezone.now()
        
        # Check that failures were reset
        assert mfa_method.token_failures == 0
        
        # Check that email was sent
        mock_send.assert_called_once()
    
    def test_generated_code_is_6_digits(self, user_with_secure_email, settings):
        """Test that the generated code is 6 digits."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Extract the code from the email call
        call_kwargs = mock_send.call_args[1]
        message = call_kwargs['message']
        
        # The code should be in the message - extract it
        # For the default template, it should be a 6-digit number
        import re
        codes = re.findall(r'\b\d{6}\b', message)
        assert len(codes) == 1
        code = codes[0]
        assert len(code) == 6
        assert code.isdigit()
    
    def test_validate_correct_code(self, user_with_secure_email, settings):
        """Test that validation succeeds with correct code."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate and send code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Extract the code from the email
        call_kwargs = mock_send.call_args[1]
        message = call_kwargs['message']
        import re
        code = re.findall(r'\b\d{6}\b', message)[0]
        
        # Validate the code
        assert dispatcher.validate_code(code) is True
        
        # After successful validation, token should be cleared
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is None
        assert mfa_method.token_expires_at is None
        assert mfa_method.token_failures == 0
    
    def test_validate_incorrect_code(self, user_with_secure_email, settings):
        """Test that validation fails with incorrect code."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate and send code
        with patch('trench.backends.secure_mail.send_mail'):
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Try with wrong code
        assert dispatcher.validate_code("999999") is False
        
        # Token should still exist
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is not None
        
        # Failure counter should increment
        assert mfa_method.token_failures == 1
    
    def test_code_is_single_use(self, user_with_secure_email, settings):
        """Test that code can only be used once."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate and send code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Extract the code
        call_kwargs = mock_send.call_args[1]
        message = call_kwargs['message']
        import re
        code = re.findall(r'\b\d{6}\b', message)[0]
        
        # First validation should succeed
        assert dispatcher.validate_code(code) is True
        
        # Second validation with same code should fail
        assert dispatcher.validate_code(code) is False
    
    def test_expired_token_rejected(self, user_with_secure_email, settings):
        """Test that expired tokens are rejected."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate and send code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Extract the code
        call_kwargs = mock_send.call_args[1]
        message = call_kwargs['message']
        import re
        code = re.findall(r'\b\d{6}\b', message)[0]
        
        # Manually expire the token
        mfa_method.refresh_from_db()
        mfa_method.token_expires_at = timezone.now() - timedelta(seconds=1)
        mfa_method.save()
        
        # Validation should fail
        assert dispatcher.validate_code(code) is False
        
        # Token should be cleared
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is None
    
    def test_max_failures_locks_token(self, user_with_secure_email, settings):
        """Test that token is locked after max failures."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate and send code
        with patch('trench.backends.secure_mail.send_mail'):
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Try wrong code 5 times (MAX_TOKEN_FAILURES)
        for i in range(5):
            assert dispatcher.validate_code("999999") is False
            mfa_method.refresh_from_db()
            assert mfa_method.token_failures == i + 1
        
        # Token should still exist but with 5 failures
        assert mfa_method.token_hash is not None
        
        # Next attempt should clear the token
        assert dispatcher.validate_code("999999") is False
        
        # Token should be cleared
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash is None
        assert mfa_method.token_failures == 0
    
    def test_new_dispatch_invalidates_old_code(self, user_with_secure_email, settings):
        """Test that generating a new code invalidates the old one."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate first code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
            
            # Extract first code
            call_kwargs = mock_send.call_args[1]
            message1 = call_kwargs['message']
            import re
            code1 = re.findall(r'\b\d{6}\b', message1)[0]
        
        # Generate second code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher.dispatch_message()
            
            # Extract second code
            call_kwargs = mock_send.call_args[1]
            message2 = call_kwargs['message']
            code2 = re.findall(r'\b\d{6}\b', message2)[0]
        
        # Codes should be different (with very high probability)
        assert code1 != code2
        
        # First code should no longer work
        assert dispatcher.validate_code(code1) is False
        
        # Second code should work
        assert dispatcher.validate_code(code2) is True
    
    def test_no_token_validation_fails(self, user_with_secure_email, settings):
        """Test that validation fails when no token exists."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
        
        # Try to validate without generating a code first
        assert dispatcher.validate_code("123456") is False
    
    def test_code_hash_not_reversible(self, user_with_secure_email, settings):
        """Test that we store hash, not plaintext code."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate code
        with patch('trench.backends.secure_mail.send_mail') as mock_send:
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
            
            # Extract the code
            call_kwargs = mock_send.call_args[1]
            message = call_kwargs['message']
            import re
            code = re.findall(r'\b\d{6}\b', message)[0]
        
        # Check that hash is different from code
        mfa_method.refresh_from_db()
        assert mfa_method.token_hash != code
        
        # Hash should be 64 hex characters (SHA-256)
        assert len(mfa_method.token_hash) == 64
        assert all(c in '0123456789abcdef' for c in mfa_method.token_hash)
    
    def test_create_code_raises_error(self, user_with_secure_email, settings):
        """Test that create_code() is not supported."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
        
        with pytest.raises(NotImplementedError):
            dispatcher.create_code()
    
    def test_concurrent_dispatch_thread_safe(self, user_with_secure_email, settings):
        """Test that concurrent dispatch is thread-safe with select_for_update."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # This test verifies that we use select_for_update
        # We'll mock the queryset to ensure select_for_update is called
        with patch('trench.backends.secure_mail.send_mail'):
            with patch.object(
                MFAMethod.objects,
                'select_for_update',
                wraps=MFAMethod.objects.select_for_update
            ) as mock_select:
                dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
                dispatcher.dispatch_message()
                
                # Verify select_for_update was called
                assert mock_select.called
    
    def test_custom_token_validity(self, user_with_secure_email, settings):
        """Test that custom TOKEN_VALIDITY is respected."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"].copy()
        config['TOKEN_VALIDITY'] = 300  # 5 minutes
        
        with patch('trench.backends.secure_mail.send_mail'):
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            before = timezone.now()
            dispatcher.dispatch_message()
            after = timezone.now()
        
        mfa_method.refresh_from_db()
        
        # Token should expire in approximately 5 minutes
        expected_expiry = before + timedelta(seconds=300)
        time_diff = abs((mfa_method.token_expires_at - expected_expiry).total_seconds())
        assert time_diff < 2  # Within 2 seconds
    
    def test_failure_counter_reset_on_new_dispatch(self, user_with_secure_email, settings):
        """Test that failure counter is reset when new code is generated."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate first code
        with patch('trench.backends.secure_mail.send_mail'):
            dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
            dispatcher.dispatch_message()
        
        # Try wrong code a few times
        dispatcher.validate_code("111111")
        dispatcher.validate_code("222222")
        
        mfa_method.refresh_from_db()
        assert mfa_method.token_failures == 2
        
        # Generate new code
        with patch('trench.backends.secure_mail.send_mail'):
            dispatcher.dispatch_message()
        
        # Failures should be reset
        mfa_method.refresh_from_db()
        assert mfa_method.token_failures == 0
    
    def test_codes_are_unique_across_dispatches(self, user_with_secure_email, settings):
        """Test that multiple dispatches generate different codes."""
        user, mfa_method = user_with_secure_email
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        codes = set()
        
        # Generate 10 codes
        for _ in range(10):
            with patch('trench.backends.secure_mail.send_mail') as mock_send:
                dispatcher = SecureMailMessageDispatcher(mfa_method=mfa_method, config=config)
                dispatcher.dispatch_message()
                
                # Extract code
                call_kwargs = mock_send.call_args[1]
                message = call_kwargs['message']
                import re
                code = re.findall(r'\b\d{6}\b', message)[0]
                codes.add(code)
        
        # All codes should be unique (with very high probability)
        # With 1,000,000 possible 6-digit codes and only 10 samples,
        # collision probability is extremely low
        assert len(codes) == 10
    
    def test_hash_uses_salt_prevents_rainbow_table(self, settings):
        """Test that hashing uses salt to prevent rainbow table attacks."""
        # Create two different users with different secrets
        user1, _ = User.objects.get_or_create(
            username="user1",
            email="user1@test.com",
        )
        user2, _ = User.objects.get_or_create(
            username="user2", 
            email="user2@test.com",
        )
        
        # Create MFA methods with different secrets (salts)
        mfa1, _ = MFAMethod.objects.get_or_create(
            user=user1,
            name="secure_email",
            defaults={
                'secret': create_secret_command(),
                'is_primary': True,
                'is_active': True,
            }
        )
        
        mfa2, _ = MFAMethod.objects.get_or_create(
            user=user2,
            name="secure_email",
            defaults={
                'secret': create_secret_command(),
                'is_primary': True,
                'is_active': True,
            }
        )
        
        # Ensure secrets are different
        assert mfa1.secret != mfa2.secret
        
        config = settings.TRENCH_AUTH["MFA_METHODS"]["secure_email"]
        
        # Generate the same code for both users (by mocking _generate_code)
        test_code = "123456"
        
        with patch('trench.backends.secure_mail.send_mail'):
            # User 1
            dispatcher1 = SecureMailMessageDispatcher(mfa_method=mfa1, config=config)
            with patch.object(dispatcher1, '_generate_code', return_value=test_code):
                dispatcher1.dispatch_message()
            
            # User 2
            dispatcher2 = SecureMailMessageDispatcher(mfa_method=mfa2, config=config)
            with patch.object(dispatcher2, '_generate_code', return_value=test_code):
                dispatcher2.dispatch_message()
        
        # Refresh from DB
        mfa1.refresh_from_db()
        mfa2.refresh_from_db()
        
        # Even though the same code was generated, the hashes should be different
        # because each user has a different secret (salt)
        assert mfa1.token_hash != mfa2.token_hash
        
        # Verify each user can only validate with their own code
        assert dispatcher1.validate_code(test_code) is True
        assert dispatcher2.validate_code(test_code) is True
        
        # This demonstrates that:
        # 1. Same code produces different hashes for different users (salt works)
        # 2. An attacker can't pre-compute a single rainbow table for all users
        # 3. Each user's validation uses their own salt correctly


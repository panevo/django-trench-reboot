import pytest
import time

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from trench.backends.email import EmailMessageDispatcher
from trench.models import OneTimeCode


User = get_user_model()


@pytest.mark.django_db
def test_email_backend_generates_unique_codes(active_user_with_email_otp, settings):
    """Test that email backend generates different codes on subsequent requests."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate first code
    code1 = dispatcher.create_code()
    
    # Generate second code immediately after
    code2 = dispatcher.create_code()
    
    # Codes should be different (or at least very likely to be different with random generation)
    # Note: There's a tiny probability they could be the same, but it's astronomically low
    assert code1 != code2, "Generated codes should be different"


@pytest.mark.django_db
def test_email_backend_stores_code_in_database(active_user_with_email_otp, settings):
    """Test that generated codes are stored in the database."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate a code
    code = dispatcher.create_code()
    
    # Verify it's stored in the database
    otc = OneTimeCode.objects.get(mfa_method=auth_method, code=code)
    assert otc is not None
    assert otc.is_used is False
    assert otc.expires_at > timezone.now()


@pytest.mark.django_db
def test_email_backend_code_validation_success(active_user_with_email_otp, settings):
    """Test that a valid code can be successfully validated."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate a code
    code = dispatcher.create_code()
    
    # Validate the code
    is_valid = dispatcher.validate_code(code)
    assert is_valid is True
    
    # After validation, the code should be marked as used
    otc = OneTimeCode.objects.get(mfa_method=auth_method, code=code)
    assert otc.is_used is True


@pytest.mark.django_db
def test_email_backend_code_cannot_be_reused(active_user_with_email_otp, settings):
    """Test that a code can only be used once."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate a code
    code = dispatcher.create_code()
    
    # Use it once - should succeed
    is_valid = dispatcher.validate_code(code)
    assert is_valid is True
    
    # Try to use it again - should fail
    is_valid = dispatcher.validate_code(code)
    assert is_valid is False


@pytest.mark.django_db
def test_email_backend_invalid_code_fails(active_user_with_email_otp, settings):
    """Test that an invalid code fails validation."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Try to validate a code that was never generated
    is_valid = dispatcher.validate_code("999999")
    assert is_valid is False


@pytest.mark.django_db
def test_email_backend_expired_code_fails(active_user_with_email_otp, settings):
    """Test that an expired code fails validation."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate a code
    code = dispatcher.create_code()
    
    # Manually expire the code by setting expires_at to the past
    otc = OneTimeCode.objects.get(mfa_method=auth_method, code=code)
    otc.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    otc.save()
    
    # Validation should fail
    is_valid = dispatcher.validate_code(code)
    assert is_valid is False


@pytest.mark.django_db
def test_email_backend_new_code_invalidates_previous(active_user_with_email_otp, settings):
    """Test that generating a new code invalidates any previous unused codes."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate first code
    code1 = dispatcher.create_code()
    
    # Generate second code (should invalidate first)
    code2 = dispatcher.create_code()
    
    # First code should now be marked as used
    otc1 = OneTimeCode.objects.get(mfa_method=auth_method, code=code1)
    assert otc1.is_used is True
    
    # Second code should still be valid
    otc2 = OneTimeCode.objects.get(mfa_method=auth_method, code=code2)
    assert otc2.is_used is False
    
    # Trying to validate the first code should fail
    is_valid = dispatcher.validate_code(code1)
    assert is_valid is False
    
    # Validating the second code should succeed
    is_valid = dispatcher.validate_code(code2)
    assert is_valid is True


@pytest.mark.django_db
def test_email_backend_dispatch_sends_email(active_user_with_email_otp, settings):
    """Test that dispatch_message sends an email with the code."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Dispatch message
    response = dispatcher.dispatch_message()
    
    # Check that email was sent
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [active_user_with_email_otp.email]
    
    # Check that response indicates success
    assert response.status_code == 200


@pytest.mark.django_db
def test_email_backend_code_format(active_user_with_email_otp, settings):
    """Test that generated codes are 6-digit numeric strings."""
    auth_method = active_user_with_email_otp.mfa_methods.get(name="email")
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher = EmailMessageDispatcher(mfa_method=auth_method, config=conf)
    
    # Generate multiple codes to ensure they all follow the format
    for _ in range(10):
        code = dispatcher.create_code()
        assert len(code) == 6, f"Code {code} should be 6 characters long"
        assert code.isdigit(), f"Code {code} should be numeric"


@pytest.mark.django_db
def test_email_backend_multiple_users_can_have_same_code(settings):
    """Test that different users can receive the same code value (security is per-user)."""
    # Create two users with email MFA
    user1, _ = User.objects.get_or_create(
        username="user1", email="user1@test.com"
    )
    user1.set_password("password")
    user1.is_active = True
    user1.save()
    
    user2, _ = User.objects.get_or_create(
        username="user2", email="user2@test.com"
    )
    user2.set_password("password")
    user2.is_active = True
    user2.save()
    
    from trench.command.create_secret import create_secret_command
    
    # Create MFA methods for both users
    from django.apps import apps
    MFAMethod = apps.get_model("trench.MFAMethod")
    
    auth_method1 = MFAMethod.objects.create(
        user=user1,
        secret=create_secret_command(),
        is_primary=True,
        name="email",
        is_active=True,
    )
    
    auth_method2 = MFAMethod.objects.create(
        user=user2,
        secret=create_secret_command(),
        is_primary=True,
        name="email",
        is_active=True,
    )
    
    conf = settings.TRENCH_AUTH["MFA_METHODS"]["email"]
    dispatcher1 = EmailMessageDispatcher(mfa_method=auth_method1, config=conf)
    dispatcher2 = EmailMessageDispatcher(mfa_method=auth_method2, config=conf)
    
    # Manually create the same code for both users (simulating collision)
    same_code = "123456"
    OneTimeCode.objects.create_code(
        mfa_method=auth_method1,
        code=same_code,
        validity_period=300,
    )
    OneTimeCode.objects.create_code(
        mfa_method=auth_method2,
        code=same_code,
        validity_period=300,
    )
    
    # User1 validates their code - should succeed
    is_valid1 = dispatcher1.validate_code(same_code)
    assert is_valid1 is True
    
    # User2 validates their code - should still succeed (not affected by user1's validation)
    is_valid2 = dispatcher2.validate_code(same_code)
    assert is_valid2 is True
    
    # Both codes should be marked as used for their respective methods
    otc1 = OneTimeCode.objects.get(mfa_method=auth_method1, code=same_code)
    assert otc1.is_used is True
    
    otc2 = OneTimeCode.objects.get(mfa_method=auth_method2, code=same_code)
    assert otc2.is_used is True

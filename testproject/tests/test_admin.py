import pytest

from django.contrib.admin import site

from trench.admin import MFAMethodAdmin
from trench.models import MFAMethod


@pytest.mark.django_db
class TestMFAMethodAdmin:
    def test_sensitive_fields_are_excluded_from_admin(
        self, admin_user, active_user_with_application_otp
    ):
        """
        Test that sensitive fields (secret and backup codes) are not displayed
        in the admin portal to prevent security vulnerabilities.
        """
        mfa_admin = MFAMethodAdmin(MFAMethod, site)

        # Check that secret and _backup_codes are excluded from the admin
        assert "secret" in mfa_admin.exclude
        assert "_backup_codes" in mfa_admin.exclude

        # Check that secret and _backup_codes are not in readonly_fields
        assert "secret" not in mfa_admin.readonly_fields
        assert "_backup_codes" not in mfa_admin.readonly_fields

    def test_sensitive_fields_not_in_fieldsets(
        self, admin_user, active_user_with_application_otp
    ):
        """
        Test that sensitive fields are not included in any fieldsets.
        """
        mfa_admin = MFAMethodAdmin(MFAMethod, site)

        # Extract all fields from fieldsets
        fieldset_fields = []
        for fieldset_name, fieldset_options in mfa_admin.fieldsets:
            fieldset_fields.extend(fieldset_options.get("fields", []))

        # Check that secret and _backup_codes are not in any fieldset
        assert "secret" not in fieldset_fields
        assert "_backup_codes" not in fieldset_fields

    def test_admin_displays_non_sensitive_fields(
        self, admin_user, active_user_with_application_otp
    ):
        """
        Test that non-sensitive fields are still displayed in the admin.
        """
        mfa_admin = MFAMethodAdmin(MFAMethod, site)

        # Extract all fields from fieldsets
        fieldset_fields = []
        for fieldset_name, fieldset_options in mfa_admin.fieldsets:
            fieldset_fields.extend(fieldset_options.get("fields", []))

        # Check that non-sensitive fields are displayed
        assert "user" in fieldset_fields
        assert "name" in fieldset_fields
        assert "is_primary" in fieldset_fields
        assert "is_active" in fieldset_fields

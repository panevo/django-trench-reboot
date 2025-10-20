from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from trench.models import MFAMethod


@admin.register(MFAMethod)
class MFAMethodAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "name",
        "is_primary",
        "is_active",
        "token_status",
        "token_failure_count",
    ]
    list_filter = ["is_primary", "is_active", "name"]
    search_fields = ["user__username", "user__email", "name"]
    readonly_fields = [
        "token_expires_at",
        "token_failures",
    ]
    # Exclude sensitive fields from admin to prevent security issues
    exclude = ["token_hash", "secret", "_backup_codes"]

    fieldsets = (
        (None, {"fields": ("user", "name", "is_primary", "is_active")}),
        (
            _("Single-Use Token (Secure Email)"),
            {
                "fields": ("token_expires_at", "token_failures"),
                "description": _(
                    "Used for secure email MFA. Token hash is never "
                    "displayed for security."
                ),
            },
        ),
    )

    @admin.display(description=_("Token Status"))
    def token_status(self, obj):
        """Display the status of the single-use token."""
        if not obj.token_hash:
            return format_html('<span style="color: gray;">{}</span>', _("No token"))

        if obj.token_expires_at:
            if timezone.now() > obj.token_expires_at:
                return format_html('<span style="color: red;">{}</span>', _("Expired"))
            else:
                time_left = obj.token_expires_at - timezone.now()
                minutes = int(time_left.total_seconds() / 60)
                return format_html(
                    '<span style="color: green;">{} ({}m left)</span>',
                    _("Valid"),
                    minutes,
                )

        return format_html('<span style="color: orange;">{}</span>', _("No expiry set"))

    @admin.display(description=_("Token Failures"))
    def token_failure_count(self, obj):
        """Display the number of failed token validation attempts."""
        if obj.token_failures == 0:
            return format_html('<span style="color: green;">{}</span>', "0")
        elif obj.token_failures >= 5:  # MAX_TOKEN_FAILURES
            return format_html(
                '<span style="color: red; font-weight: bold;">{} (locked)</span>',
                obj.token_failures,
            )
        else:
            return format_html(
                '<span style="color: orange;">{}</span>', obj.token_failures
            )

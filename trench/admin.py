from django.contrib import admin

from trench.models import MFAMethod, OneTimeCode


@admin.register(MFAMethod)
class MFAMethodAdmin(admin.ModelAdmin):
    pass


@admin.register(OneTimeCode)
class OneTimeCodeAdmin(admin.ModelAdmin):
    list_display = ["mfa_method", "code", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used", "created_at", "expires_at"]
    readonly_fields = ["created_at"]
    search_fields = ["code", "mfa_method__user__username"]

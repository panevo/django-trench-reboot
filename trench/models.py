from django.conf import settings
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    ForeignKey,
    Manager,
    Model,
    Q,
    QuerySet,
    TextField,
    UniqueConstraint,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from typing import Any, Iterable

from trench.exceptions import MFAMethodDoesNotExistError


class MFAUserMethodManager(Manager):
    def get_by_name(self, user_id: Any, name: str) -> "MFAMethod":
        try:
            return self.get(user_id=user_id, name=name)
        except self.model.DoesNotExist:
            raise MFAMethodDoesNotExistError()

    def get_primary_active(self, user_id: Any) -> "MFAMethod":
        try:
            return self.get(user_id=user_id, is_primary=True, is_active=True)
        except self.model.DoesNotExist:
            raise MFAMethodDoesNotExistError()

    def get_primary_active_name(self, user_id: Any) -> str:
        method_name = (
            self.filter(user_id=user_id, is_primary=True, is_active=True)
            .values_list("name", flat=True)
            .first()
        )
        if method_name is None:
            raise MFAMethodDoesNotExistError()
        return method_name

    def is_active_by_name(self, user_id: Any, name: str) -> bool:
        is_active = (
            self.filter(user_id=user_id, name=name)
            .values_list("is_active", flat=True)
            .first()
        )
        if is_active is None:
            raise MFAMethodDoesNotExistError()
        return is_active

    def list_active(self, user_id: Any) -> QuerySet:
        return self.filter(user_id=user_id, is_active=True)

    def primary_exists(self, user_id: Any) -> bool:
        return self.filter(user_id=user_id, is_primary=True).exists()


class MFAMethod(Model):
    _BACKUP_CODES_DELIMITER = "|"

    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=CASCADE,
        verbose_name=_("user"),
        related_name="mfa_methods",
    )
    name = CharField(_("name"), max_length=255)
    secret = CharField(_("secret"), max_length=255)
    is_primary = BooleanField(_("is primary"), default=False)
    is_active = BooleanField(_("is active"), default=False)
    _backup_codes = TextField(_("backup codes"), blank=True)

    class Meta:
        verbose_name = _("MFA Method")
        verbose_name_plural = _("MFA Methods")
        constraints = (
            UniqueConstraint(
                fields=("user", "name"),
                name="unique_user_method_name",
            ),
            UniqueConstraint(
                condition=Q(is_primary=True),
                fields=("user",),
                name="unique_user_is_primary",
            ),
            CheckConstraint(
                check=(Q(is_primary=True) & Q(is_active=True)) | Q(is_primary=False),
                name="primary_is_active",
            ),
        )

    objects = MFAUserMethodManager()

    def __str__(self) -> str:
        return f"{self.name} (User id: {self.user_id})"

    @property
    def backup_codes(self) -> Iterable[str]:
        return self._backup_codes.split(self._BACKUP_CODES_DELIMITER)

    @backup_codes.setter
    def backup_codes(self, codes: Iterable) -> None:
        self._backup_codes = self._BACKUP_CODES_DELIMITER.join(codes)


class OneTimeCodeManager(Manager):
    def create_code(self, mfa_method: MFAMethod, code: str, validity_period: int) -> "OneTimeCode":
        """Create a new one-time code with expiry."""
        # Invalidate any existing codes for this method
        self.filter(mfa_method=mfa_method, is_used=False).update(is_used=True)
        
        expires_at = timezone.now() + timezone.timedelta(seconds=validity_period)
        return self.create(
            mfa_method=mfa_method,
            code=code,
            expires_at=expires_at,
        )
    
    def validate_and_use(self, mfa_method: MFAMethod, code: str) -> bool:
        """Validate a code and mark it as used if valid."""
        try:
            otc = self.get(
                mfa_method=mfa_method,
                code=code,
                is_used=False,
                expires_at__gt=timezone.now(),
            )
            otc.is_used = True
            otc.save(update_fields=["is_used"])
            return True
        except self.model.DoesNotExist:
            return False


class OneTimeCode(Model):
    """Model to store single-use verification codes for email MFA."""
    
    mfa_method = ForeignKey(
        MFAMethod,
        on_delete=CASCADE,
        verbose_name=_("MFA method"),
        related_name="one_time_codes",
    )
    code = CharField(_("code"), max_length=255)
    created_at = DateTimeField(_("created at"), auto_now_add=True)
    expires_at = DateTimeField(_("expires at"))
    is_used = BooleanField(_("is used"), default=False)
    
    objects = OneTimeCodeManager()
    
    class Meta:
        verbose_name = _("One-Time Code")
        verbose_name_plural = _("One-Time Codes")
        indexes = [
            # Index for quick lookups during validation
            # Note: Django will automatically create indexes for foreign keys
        ]
    
    def __str__(self) -> str:
        return f"Code for {self.mfa_method} (expires: {self.expires_at})"
    
    def is_valid(self) -> bool:
        """Check if the code is still valid."""
        return not self.is_used and self.expires_at > timezone.now()

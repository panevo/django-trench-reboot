from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

import logging
import secrets
from smtplib import SMTPException

from trench.backends.base import AbstractMessageDispatcher
from trench.models import OneTimeCode
from trench.responses import (
    DispatchResponse,
    FailedDispatchResponse,
    SuccessfulDispatchResponse,
)
from trench.settings import EMAIL_HTML_TEMPLATE, EMAIL_PLAIN_TEMPLATE, EMAIL_SUBJECT


class EmailMessageDispatcher(AbstractMessageDispatcher):
    """
    Email backend that generates single-use random codes instead of TOTP codes.
    
    This backend creates a random numeric code that is stored in the database
    with an expiration timestamp. The code can only be used once and expires
    after the validity period.
    """
    _KEY_MESSAGE = "message"
    _SUCCESS_DETAILS = _("Email message with MFA code has been sent.")
    
    def create_code(self) -> str:
        """Generate a cryptographically secure random 6-digit code."""
        # Generate a random 6-digit code using secrets for cryptographic strength
        code = str(secrets.randbelow(1000000)).zfill(6)
        
        # Store the code in the database with expiration
        OneTimeCode.objects.create_code(
            mfa_method=self._mfa_method,
            code=code,
            validity_period=self._get_valid_window(),
        )
        
        return code

    def validate_code(self, code: str) -> bool:
        """
        Validate a code by checking if it exists, is unused, and not expired.
        If valid, mark it as used.
        """
        return OneTimeCode.objects.validate_and_use(
            mfa_method=self._mfa_method,
            code=code,
        )

    def dispatch_message(self) -> DispatchResponse:
        context = {"code": self.create_code()}
        email_plain_template = self._config[EMAIL_PLAIN_TEMPLATE]
        email_html_template = self._config[EMAIL_HTML_TEMPLATE]
        try:
            send_mail(
                subject=self._config.get(EMAIL_SUBJECT),
                message=get_template(email_plain_template).render(context),
                html_message=get_template(email_html_template).render(context),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=(self._to,),
                fail_silently=False,
            )
            return SuccessfulDispatchResponse(details=self._SUCCESS_DETAILS)
        except SMTPException as cause:  # pragma: nocover
            logging.error(cause, exc_info=True)  # pragma: nocover
            return FailedDispatchResponse(details=str(cause))  # pragma: nocover
        except ConnectionRefusedError as cause:  # pragma: nocover
            logging.error(cause, exc_info=True)  # pragma: nocover
            return FailedDispatchResponse(details=str(cause))  # pragma: nocover

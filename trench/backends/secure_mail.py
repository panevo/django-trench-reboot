from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import get_template
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import hashlib
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException

from trench.backends.base import AbstractMessageDispatcher
from trench.responses import (
    DispatchResponse,
    FailedDispatchResponse,
    SuccessfulDispatchResponse,
)
from trench.settings import EMAIL_HTML_TEMPLATE, EMAIL_PLAIN_TEMPLATE, EMAIL_SUBJECT


# Maximum number of failed attempts before token is invalidated
MAX_TOKEN_FAILURES = 5

# Token validity duration in seconds (default 10 minutes)
DEFAULT_TOKEN_VALIDITY = 600


class SecureMailMessageDispatcher(AbstractMessageDispatcher):
    """
    Secure email MFA backend that generates single-use random codes.

    Unlike the basic email backend which uses TOTP codes that are valid for
    multiple uses within a time window, this backend generates a cryptographically
    secure random code for each request. The code is hashed before storage and
    can only be used once.

    Features:
    - Generates random 6-digit codes using secrets module (cryptographically secure)
    - Hashes codes using SHA-256 before storing in database
    - Enforces single-use: code is invalidated after successful validation
    - Implements expiration: codes expire after configured time period
    - Tracks failed attempts and locks out after MAX_TOKEN_FAILURES
    - Thread-safe: uses select_for_update to prevent race conditions
    - Never logs codes in plaintext
    """

    _KEY_MESSAGE = "message"
    _SUCCESS_DETAILS = _("Email message with MFA code has been sent.")
    _TOKEN_LENGTH = 6  # 6 digits = 1,000,000 possible codes

    def dispatch_message(self) -> DispatchResponse:
        """
        Generate a new single-use code, hash it, store it, and send via email.

        Each call to this method generates a new code and invalidates any
        previously issued code for this MFA method.
        """
        # Generate a cryptographically secure random code
        code = self._generate_code()

        # Hash the code before storing
        code_hash = self._hash_code(code)

        # Calculate expiration time
        validity_seconds = self._config.get("TOKEN_VALIDITY", DEFAULT_TOKEN_VALIDITY)
        expires_at = timezone.now() + timedelta(seconds=validity_seconds)

        # Store the hashed code with expiration and reset failure counter
        # Use select_for_update to prevent race conditions
        try:
            with transaction.atomic():
                mfa_method = self._mfa_method.__class__.objects.select_for_update().get(
                    pk=self._mfa_method.pk
                )
                mfa_method.token_hash = code_hash
                mfa_method.token_expires_at = expires_at
                mfa_method.token_failures = 0
                mfa_method.save(
                    update_fields=["token_hash", "token_expires_at", "token_failures"]
                )
        except Exception as cause:  # pragma: nocover
            logging.error(
                "Failed to store token for MFA method %s: %s",
                self._mfa_method.name,
                cause,
                exc_info=True,
            )  # pragma: nocover
            return FailedDispatchResponse(
                details=_("Failed to generate verification code")
            )  # pragma: nocover

        # Send the code via email (NOT the hash)
        context = {"code": code}
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
            logging.info(
                "Sent verification code to %s for MFA method %s (user_id=%s)",
                self._to,
                self._mfa_method.name,
                self._mfa_method.user_id,
            )
            return SuccessfulDispatchResponse(details=self._SUCCESS_DETAILS)
        except SMTPException as cause:  # pragma: nocover
            logging.error(
                "SMTP error sending code to %s: %s", self._to, cause, exc_info=True
            )  # pragma: nocover
            return FailedDispatchResponse(details=str(cause))  # pragma: nocover
        except ConnectionRefusedError as cause:  # pragma: nocover
            logging.error(
                "Connection refused sending code to %s: %s",
                self._to,
                cause,
                exc_info=True,
            )  # pragma: nocover
            return FailedDispatchResponse(details=str(cause))  # pragma: nocover

    def _generate_code(self) -> str:
        """
        Generate a cryptographically secure random numeric code.

        Uses the secrets module which is appropriate for security-sensitive
        applications.

        Returns:
            A string of TOKEN_LENGTH digits
        """
        # Generate random integer in range [0, 10^TOKEN_LENGTH)
        # For TOKEN_LENGTH=6, this is [0, 1000000), giving codes 000000-999999
        max_value = 10**self._TOKEN_LENGTH
        code_int = secrets.randbelow(max_value)

        # Format with leading zeros
        return str(code_int).zfill(self._TOKEN_LENGTH)

    def _hash_code(self, code: str) -> str:
        """
        Hash a code using SHA-256 with the MFA method's secret as salt.

        Even though the code space is small (1 million codes), an attacker with
        database access could pre-compute all hashes and reverse them. Using the
        MFA method's secret as a per-user salt prevents this rainbow table attack.

        Args:
            code: The plaintext code to hash

        Returns:
            The SHA-256 hash as a hexadecimal string (64 characters)
        """
        # Use the MFA method's secret as salt (unique per user and per MFA method)
        salt = self._mfa_method.secret

        # Combine salt and code before hashing
        salted_code = f"{salt}{code}"
        return hashlib.sha256(salted_code.encode("utf-8")).hexdigest()

    def validate_code(self, code: str) -> bool:
        """
        Validate a code against the stored hashed token.

        This method:
        1. Checks if a token exists
        2. Checks if the token has expired
        3. Checks if too many failed attempts have occurred
        4. Validates the code against the stored hash
        5. On success: clears the token (single-use)
        6. On failure: increments failure counter

        Args:
            code: The plaintext code to validate

        Returns:
            True if the code is valid, False otherwise
        """
        # Use select_for_update to prevent race conditions
        with transaction.atomic():
            mfa_method = self._mfa_method.__class__.objects.select_for_update().get(
                pk=self._mfa_method.pk
            )

            # Check if token exists
            if not mfa_method.token_hash:
                logging.warning(
                    "Validation attempted but no token exists for MFA method %s (user_id=%s)",
                    mfa_method.name,
                    mfa_method.user_id,
                )
                return False

            # Check if token has expired
            if (
                mfa_method.token_expires_at
                and timezone.now() > mfa_method.token_expires_at
            ):
                logging.warning(
                    "Validation attempted with expired token for MFA method %s (user_id=%s)",
                    mfa_method.name,
                    mfa_method.user_id,
                )
                # Clear expired token
                mfa_method.token_hash = None
                mfa_method.token_expires_at = None
                mfa_method.token_failures = 0
                mfa_method.save(
                    update_fields=["token_hash", "token_expires_at", "token_failures"]
                )
                return False

            # Check if too many failures
            if mfa_method.token_failures >= MAX_TOKEN_FAILURES:
                logging.warning(
                    "Validation attempted but max failures reached for MFA method %s (user_id=%s)",
                    mfa_method.name,
                    mfa_method.user_id,
                )
                # Clear token after too many failures
                mfa_method.token_hash = None
                mfa_method.token_expires_at = None
                mfa_method.token_failures = 0
                mfa_method.save(
                    update_fields=["token_hash", "token_expires_at", "token_failures"]
                )
                return False

            # Hash the provided code with the same salt used during generation
            code_hash = self._hash_code(code)

            if code_hash == mfa_method.token_hash:
                # Success! Clear the token (single-use)
                logging.info(
                    "Successful validation for MFA method %s (user_id=%s)",
                    mfa_method.name,
                    mfa_method.user_id,
                )
                mfa_method.token_hash = None
                mfa_method.token_expires_at = None
                mfa_method.token_failures = 0
                mfa_method.save(
                    update_fields=["token_hash", "token_expires_at", "token_failures"]
                )
                return True
            else:
                # Failed validation, increment counter
                mfa_method.token_failures += 1
                mfa_method.save(update_fields=["token_failures"])
                logging.warning(
                    "Failed validation attempt %d/%d for MFA method %s (user_id=%s)",
                    mfa_method.token_failures,
                    MAX_TOKEN_FAILURES,
                    mfa_method.name,
                    mfa_method.user_id,
                )
                return False

    def create_code(self) -> str:
        """
        Override base class method to ensure we don't use TOTP.

        This method should not be called for this backend - we generate
        codes in dispatch_message(). However, if it is called, we'll
        raise an error to make it clear this backend doesn't work that way.
        """
        raise NotImplementedError(
            "SecureMailMessageDispatcher does not support create_code(). "
            "Codes are generated and stored during dispatch_message()."
        )

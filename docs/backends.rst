Authentication backends
=======================

| ``django-trench`` comes with some predefined authentication methods.
| Custom backends can be easily added by inheriting from ``AbstractMessageDispatcher`` class.

Built-in backends
"""""""""""""""""

E-mail
*****

**Two email backends are available:**

Basic Email (TOTP-based)
-------------------------

This basic method uses built-in Django email backend with TOTP code generation.
The same code is generated for multiple requests within a time window.

.. code-block:: python

    TRENCH_AUTH = {
        (...)
        'MFA_METHODS': {
            'email': {
                'VERBOSE_NAME': 'email',
                'VALIDITY_PERIOD': 60 * 10,
                'HANDLER': 'trench.backends.basic_mail.SendMailBackend',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
            },
            ...,
        },
    }

``EMAIL_PLAIN_TEMPLATE`` and ``EMAIL_HTML_TEMPLATE`` are paths to templates
that are used to render email content.

These templates receive ``code`` variable in the context, which is the generated OTP code.

**⚠️ Security Note:** The basic email backend uses TOTP, which means the same code
is generated for multiple requests within the validity period. This is a security
vulnerability. Consider using the Secure Email backend instead.

Secure Email (Single-Use Codes)
--------------------------------

This enhanced method generates cryptographically secure, single-use random codes
for each authentication request. This is the **recommended backend** for email MFA
as it addresses security vulnerabilities in the basic email backend.

.. code-block:: python

    TRENCH_AUTH = {
        (...)
        'MFA_METHODS': {
            'secure_email': {
                'VERBOSE_NAME': 'secure_email',
                'HANDLER': 'trench.backends.secure_mail.SecureMailMessageDispatcher',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
                'TOKEN_VALIDITY': 600,  # 10 minutes in seconds
            },
            ...,
        },
    }

:TOKEN_VALIDITY: Time in seconds before the code expires (default: 600 = 10 minutes)

**Key Features:**

* **Single-use codes**: Each code can only be used once, even if it hasn't expired
* **Random generation**: Uses Python's ``secrets`` module for cryptographic security
* **Hashed storage**: Codes are stored as SHA-256 hashes, never in plaintext
* **Brute-force protection**: After 5 failed attempts, the token is invalidated
* **Thread-safe**: Uses ``select_for_update()`` to prevent race conditions
* **Expiration**: Codes expire after the configured validity period
* **Automatic invalidation**: Requesting a new code invalidates any previous codes

**Important Notes:**

* When a user clicks "resend", previous codes become invalid
* Users should always use the most recent code received
* Failed validation attempts are tracked and logged (but codes are never logged in plaintext)
* The admin interface shows token status and failure count, but never the actual code

**Migration from basic_email:**

The ``basic_email`` backend remains available for backward compatibility.
To migrate:

1. Update your ``TRENCH_AUTH`` settings to use ``secure_email``
2. Run migrations to add the required database fields
3. Inform users that they should use the latest code if they requested multiple codes

Text / SMS
**********

| SMS backends sends out text messages with `Twilio`_ or `SMS API`_. Credentials can be set in method's specific settings.

Using Twilio
------------

| If you are using Twilio service for sending out Text messages then you need to set ``TWILIO_ACCOUNT_SID`` and ``TWILIO_AUTH_TOKEN`` environment variables for Twilio API client to be used as credentials.

.. code-block:: python

    TRENCH_AUTH = {
        "MFA_METHODS": {
            "sms_twilio": {
                VERBOSE_NAME: _("sms_twilio"),
                VALIDITY_PERIOD: 30,
                HANDLER: "trench.backends.twilio.TwilioMessageDispatcher",
                SOURCE_FIELD: "phone_number",
                TWILIO_VERIFIED_FROM_NUMBER: "+48 123 456 789",
            },
        },
    }

:SOURCE_FIELD: Defines the field name in your ``AUTH_USER_MODEL`` to be looked up and used as field containing the phone number of the recipient of the OTP code.
:TWILIO_VERIFIED_FROM_NUMBER: This will be used as the sender's phone number. Note: this number must be verified in the Twilio's client panel.

Using SMS API
-------------

.. code-block:: python

    TRENCH_AUTH = {
        "MFA_METHODS": {
            "sms_api": {
                "VERBOSE_NAME": _("sms_api"),
                "VALIDITY_PERIOD": 30,
                "HANDLER": "trench.backends.sms_api.SMSAPIMessageDispatcher",
                "SOURCE_FIELD": "phone_number",
                "SMSAPI_ACCESS_TOKEN": "YOUR SMSAPI TOKEN",
                "SMSAPI_FROM_NUMBER": "YOUR REGISTERED NUMBER",
            }
        }
    }


:SOURCE_FIELD: Defines the field name in your ``AUTH_USER_MODEL`` to be looked up and used as field containing the phone number of the recipient of the OTP code.
:SMSAPI_ACCESS_TOKEN: Access token obtained from `SMS API`_
:SMSAPI_FROM_NUMBER: This will be used as the sender's phone number.

Authentication apps
*******************
| This backend returns OTP based QR link to be scanned by apps like Google Authenticator and Authy.

**Important note:** validity period varies between apps. Use the right value you
find in a given provider's docs. Setting the wrong value will lead to an error with
validating MFA code.

.. code-block:: python

    TRENCH_AUTH = {
        "MFA_METHODS": {
            "app": {
                "VERBOSE_NAME": _("app"),
                "VALIDITY_PERIOD": 30,
                "USES_THIRD_PARTY_CLIENT": True,
                "HANDLER": "trench.backends.application.ApplicationMessageDispatcher",
            }
        }
    }

YubiKey
*******

.. code-block:: python

    TRENCH_AUTH = {
        "MFA_METHODS": {
            "yubi": {
                "VERBOSE_NAME": _("yubi"),
                "HANDLER": "trench.backends.yubikey.YubiKeyMessageDispatcher",
                "YUBICLOUD_CLIENT_ID": "YOUR KEY",
            }
        }
    }

:YUBICLOUD_CLIENT_ID: Your client ID obtained from `Yubico`_.

Adding custom MFA backend
"""""""""""""""""""""""""

| Basing on provided examples you can create your own handler class, which inherits from ``AbstractMessageDispatcher``.

.. code-block:: python

    from trench.backends.base import AbstractMessageDispatcher


    class YourMessageDispatcher(AbstractMessageDispatcher):
        def dispatch_message(self) -> DispatchResponse:
            try:
                # dispatch the message through the channel of your choice
                return SuccessfulDispatchResponse(details=_("Code was sent."))
            except Exception as cause:
                return FailedDispatchResponse(details=str(cause))

.. _`Django's documentation`: https://docs.djangoproject.com/en/3.2/topics/email/
.. _`Twilio`: https://www.twilio.com/
.. _`SMS API`: https://www.smsapi.pl/
.. _`Yubico`: https://www.yubico.com/

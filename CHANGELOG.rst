=========
Changelog
=========

0.3.8 (Unreleased)
==================

**Security Enhancement: New Secure Email Backend**

* **Added ``secure_email`` backend**: A new email MFA backend that uses single-use random codes instead of TOTP
* **Addresses security vulnerability**: The existing ``basic_email`` backend uses TOTP codes that remain valid for multiple uses within a time window. The new ``secure_email`` backend generates cryptographically secure, single-use codes
* **Key features**:
  
  * Single-use codes that are invalidated after successful validation
  * Cryptographically secure random code generation using Python's ``secrets`` module
  * SHA-256 hashing of codes before database storage (no plaintext codes)
  * Configurable expiration (default 10 minutes)
  * Brute-force protection (5 failed attempts = lockout)
  * Thread-safe implementation using ``select_for_update()``
  * Comprehensive logging without exposing codes

* **Database changes**: Added three new fields to ``MFAMethod`` model:
  
  * ``token_hash``: SHA-256 hash of the single-use token
  * ``token_expires_at``: Expiration timestamp
  * ``token_failures``: Failed validation attempt counter

* **Admin enhancements**: Updated admin interface to display token status, expiration time, and failure count (never shows actual codes)
* **Backward compatibility**: The ``basic_email`` backend remains available and unchanged
* **Migration path**: Users can switch to ``secure_email`` by updating their ``TRENCH_AUTH`` configuration
* **Documentation**: Added comprehensive documentation for the new backend in ``backends.rst`` and ``settings.rst``
* **Tests**: Added 21 comprehensive tests covering all aspects of the secure email backend

**Migration Instructions**:

To use the new secure email backend:

1. Run migrations: ``python manage.py migrate``
2. Update your ``TRENCH_AUTH`` settings to use ``'trench.backends.secure_mail.SecureMailMessageDispatcher'`` as the handler for your email MFA method
3. Optionally configure ``TOKEN_VALIDITY`` (default: 600 seconds)

See the documentation for detailed configuration examples.


0.3.7 (2025-08-13)
==================

* Speed up second-step MFA code validation by optimizing backup code check order 


0.3.6 (2025-06-17)
==================

* Provide Django 5.x support
* Provide Python 3.13 support


0.3.5 (2025-01-20)
==================

* Fix issue with email 2FA activation


0.3.4 (2025-01-17)
==================

* Update documentation
* Support Django Rest Framework 3.15


0.3.3 (2024-05-31)
==================

* Update details for PyPi


0.3.2 (2024-05-29)
==================

* Update project details
* Provide Django 4.2 support, remove Django 2.x and Python <3.8 support


0.3.1 (2022-02-23)
==================

* Changed `n` time-windows of 1 second intervals to a single time window of `n` seconds interval
* Tests refactoring


0.3.0 (2021-04-30)
==================

* Support for Python >=3.7 only (older versions are not maintained anymore)
* Abandoned support of the :code:`django-rest-framework-jwt` library as it is no longer maintained.
* Used :code:`black` tool for auto code formatting.
* Type hints added.
* Backwards-compatible code refactoring and cleanup for better maintenance experience.
* Deactivation of primary MFA method would raise an error instead of randomly selecting new primary method from all active ones.
* Twilio backend client should be configured via environment variables instead of backend's configuration the `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`.
* :code:`djoser` integration abandoned due to infrequent updates of the library. Djoser's auth links are no longer supported.


0.2.3 (2019-12-16)
==================

* Add possibility to override default trench templates for ``SendMailBackend``.
* Remove six.test_type from ``ObtainJSONWebTokenMixin``.
* Store YubiKey ``device_id`` directly in MFAMethod model.
* Make default backup codes more secure, increase backup codes length from 6 to 12 and extend backup codes characters from only digits to ascii_letters also.
* Bump versions of packages.
* Add support for Django 3.0, Python 3.8 and DRF 3.10.
* Remove support for Python 3.4.


0.2.2 (2019-05-21)
==================

* Fix missing ``_action method`` on Token Based Authentication views.
* Bump up supported djoser version.
* Add DRF 3.9 and Django 2.2 to test environment.
* Add locale directory to distribution package.
* Change url patterns and add exception handling for method activation views.


0.2.1 (2019-03-05)
==================

* Add setting for secret_key_length and set it to default of 16.
* Replace split method on ephemeral_token with rsplit.
* Add AllowAny to the mixins for login views.
* Change ``_backup_codes`` to TextField.


0.2.0 (2019-01-15)
==================

* Add auth backend for YubiKey.
* Change default email backend to Django's built-in.
* Add sms auth backend for smsapi.pl.
* Add support for Simple JWT.
* Add encryption for backup codes with customisation setting.
* Update translations.
* Add Transifex for translations.
* Add flake8 and isort to tox tests.
* Change default settings to more verbose.
* Fix setup to install only trench package.
* Fix pytest import mistmatch error when running test in Docker.


0.1.0 (2018-11-08)
==================

* Initial release.

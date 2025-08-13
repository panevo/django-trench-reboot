=========
Changelog
=========

0.3.7 (2025-08-13)
==================

* #13 Speed up second-step MFA code validation by optimizing backup code check order 


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

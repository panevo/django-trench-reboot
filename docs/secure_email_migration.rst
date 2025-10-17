Migrating to Secure Email Backend
==================================

Overview
--------

The ``secure_email`` backend addresses a security vulnerability in the original ``basic_email`` backend. The basic email backend uses TOTP (Time-based One-Time Password) which generates the same code for multiple requests within a time window. This means:

- If a user requests a code multiple times, they receive the same code
- An attacker who intercepts one code can use it multiple times within the validity period
- The code doesn't invalidate after successful use

The ``secure_email`` backend fixes these issues by:

- Generating a unique random code for each request
- Invalidating codes after a single successful use
- Storing codes as hashes (SHA-256) rather than plaintext
- Implementing brute-force protection
- Using thread-safe database operations

Why Migrate?
------------

**Security Benefits:**

1. **Single-use codes**: Each code can only be used once, even within its validity period
2. **Random generation**: Codes are cryptographically secure random numbers
3. **No code reuse**: Requesting a new code invalidates any previous codes
4. **Brute-force protection**: After 5 failed attempts, the token is locked
5. **Secure storage**: Codes are hashed before storage (SHA-256)

**When to Migrate:**

- **Recommended for all new projects**: Use ``secure_email`` from the start
- **Recommended for existing projects**: Especially if security is a concern
- **Required if**: Your users request multiple codes frequently
- **Required if**: You need audit trail of failed attempts

Migration Steps
---------------

Step 1: Run Database Migrations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The secure email backend requires three new database fields. Run migrations:

.. code-block:: bash

    python manage.py migrate

This adds:

- ``token_hash``: Stores SHA-256 hash of the code
- ``token_expires_at``: Stores expiration timestamp
- ``token_failures``: Tracks failed validation attempts

Step 2: Update Settings
^^^^^^^^^^^^^^^^^^^^^^^^

Update your ``TRENCH_AUTH`` configuration in ``settings.py``:

**Before:**

.. code-block:: python

    TRENCH_AUTH = {
        'MFA_METHODS': {
            'email': {
                'VERBOSE_NAME': 'email',
                'VALIDITY_PERIOD': 600,
                'HANDLER': 'trench.backends.basic_mail.SendMailMessageDispatcher',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
            },
        },
    }

**After:**

.. code-block:: python

    TRENCH_AUTH = {
        'MFA_METHODS': {
            'email': {
                'VERBOSE_NAME': 'email',
                'HANDLER': 'trench.backends.secure_mail.SecureMailMessageDispatcher',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
                'TOKEN_VALIDITY': 600,  # Optional: 10 minutes (default)
            },
        },
    }

**Note:** Remove ``VALIDITY_PERIOD`` and add ``TOKEN_VALIDITY`` instead.

Step 3: Update Email Templates (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The code format and email templates remain the same. However, you may want to add a note about the single-use nature:

.. code-block:: text

    Your verification code is: {{ code }}

    This code will expire in 10 minutes and can only be used once.
    If you request a new code, this one will become invalid.

Step 4: Test the Migration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Request a verification code
2. Verify it works with the correct code
3. Try using the same code again (should fail)
4. Request a new code
5. Verify the old code no longer works

Configuration Options
---------------------

TOKEN_VALIDITY
^^^^^^^^^^^^^^

Controls how long codes remain valid (in seconds):

.. code-block:: python

    'TOKEN_VALIDITY': 600  # 10 minutes (default)
    'TOKEN_VALIDITY': 300  # 5 minutes (more secure)
    'TOKEN_VALIDITY': 900  # 15 minutes (more user-friendly)

Brute-Force Protection
^^^^^^^^^^^^^^^^^^^^^^

The backend automatically locks tokens after 5 failed attempts. This is not configurable but can be modified by editing ``MAX_TOKEN_FAILURES`` in ``trench/backends/secure_mail.py``.

Coexistence Strategy
---------------------

You can run both backends simultaneously during migration:

.. code-block:: python

    TRENCH_AUTH = {
        'MFA_METHODS': {
            'email': {  # Old backend (legacy)
                'VERBOSE_NAME': 'email',
                'VALIDITY_PERIOD': 600,
                'HANDLER': 'trench.backends.basic_mail.SendMailMessageDispatcher',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
            },
            'secure_email': {  # New backend
                'VERBOSE_NAME': 'secure_email',
                'HANDLER': 'trench.backends.secure_mail.SecureMailMessageDispatcher',
                'SOURCE_FIELD': 'email',
                'EMAIL_SUBJECT': 'Your verification code',
                'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
                'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
                'TOKEN_VALIDITY': 600,
            },
        },
    }

This allows users to gradually migrate from ``email`` to ``secure_email``.

Troubleshooting
---------------

"Code invalid" after successful login
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is expected behavior! Unlike the TOTP-based backend, secure codes are single-use. Each code can only be validated once.

Multiple code requests invalidate previous codes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is by design. When a user clicks "resend code", all previous codes become invalid. This prevents confusion and potential security issues.

**Solution:** Update your UI to warn users:
"Requesting a new code will invalidate any previously sent codes."

Token locked after failed attempts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After 5 failed validation attempts, the token is automatically locked for security. The user must request a new code.

**Solution:** Show clear error messages after 3-4 failed attempts:
"You have X attempts remaining before the code is locked."

Admin interface shows hashed token
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The admin interface shows a truncated hash, not the actual code. This is intentional - codes are never stored in plaintext.

**Solution:** This is working as designed. If you need to debug, check the email logs (but never log the actual code).

Comparison with Basic Email
----------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Feature
     - Basic Email (TOTP)
     - Secure Email
   * - Code type
     - Time-based (TOTP)
     - Random
   * - Code reuse
     - Multiple uses within window
     - Single use only
   * - Storage
     - Secret key
     - SHA-256 hash
   * - Expiration
     - Time window
     - Absolute timestamp
   * - Brute-force protection
     - No
     - Yes (5 attempts)
   * - Thread safety
     - Basic
     - select_for_update()
   * - Code invalidation on resend
     - No (same code)
     - Yes (new code)
   * - Logging
     - May log codes
     - Never logs codes

Best Practices
--------------

1. **Use secure_email for new projects**: Start with the secure backend from day one
2. **Set appropriate TOKEN_VALIDITY**: Balance security and user experience (10 minutes is good default)
3. **Update UI messages**: Inform users about single-use nature and resend behavior
4. **Monitor failed attempts**: Use admin interface to identify potential attacks
5. **Keep basic_email for compatibility**: Only if you have existing users and need time to migrate
6. **Never log codes**: Both backends avoid logging codes, maintain this in custom code
7. **Test migration**: Use staging environment to test before production deployment

Support
-------

For issues or questions about migration:

1. Check the main documentation at https://django-trench.readthedocs.io/
2. Review the test suite in ``testproject/tests/test_secure_email_*.py`` for examples
3. Open an issue at https://github.com/panevo/django-trench-reboot/issues

# HOTP Email MFA Implementation

This document describes the new HOTP (HMAC-based One-Time Password) email MFA method added to the django-trench package.

## Overview

The `HOTPSendMailMessageDispatcher` provides HOTP-based email MFA as an alternative to the existing TOTP-based methods. Unlike TOTP which uses time-based codes, HOTP uses a counter-based approach where each code is generated using an incrementing counter value.

## Key Differences from TOTP

- **Counter-based**: Uses an incrementing counter instead of time
- **Sequential codes**: Each code is unique and generated in sequence
- **No time dependency**: Codes don't expire based on time intervals
- **Synchronization**: Includes counter synchronization to handle out-of-sync scenarios

## Files Added/Modified

### New Files

- `trench/command/create_hotp.py` - HOTP creation command
- `trench/backends/hotp_base.py` - Base class for HOTP dispatchers
- `trench/backends/hotp_mail.py` - HOTP email dispatcher implementation
- `trench/migrations/0007_mfamethod_counter.py` - Database migration for counter field
- `testproject/tests/test_hotp_mail.py` - Test cases for HOTP functionality

### Modified Files

- `trench/models.py` - Added `counter` field to MFAMethod model
- `trench/settings.py` - Added `hotp_email` MFA method configuration
- `trench/backends/__init__.py` - Exported new dispatcher class

## Usage

### Configuration

Add the HOTP email method to your Django settings:

```python
TRENCH_AUTH = {
    'MFA_METHODS': {
        'hotp_email': {
            'VERBOSE_NAME': 'HOTP Email',
            'VALIDITY_PERIOD': 30,
            'HANDLER': 'trench.backends.hotp_mail.HOTPSendMailMessageDispatcher',
            'SOURCE_FIELD': 'email',
            'EMAIL_SUBJECT': 'Your HOTP verification code',
            'EMAIL_PLAIN_TEMPLATE': 'trench/backends/email/code.txt',
            'EMAIL_HTML_TEMPLATE': 'trench/backends/email/code.html',
        },
        # ... other methods
    }
}
```

### Database Migration

Run the migration to add the counter field:

```bash
python manage.py migrate trench
```

### API Usage

The HOTP email method works identically to other MFA methods from the API perspective:

1. **Activate MFA method**: Use the standard activation endpoint with `method_name="hotp_email"`
2. **Generate codes**: Codes are automatically generated and emailed when requested
3. **Validate codes**: Use the standard validation endpoint

## Implementation Details

### Counter Management

- Each MFAMethod instance has a `counter` field starting at 0
- Counter increments with each code generation
- Validation includes a synchronization window (checks up to 10 codes ahead)
- Counter updates automatically during successful validation

### Code Generation

```python
# Generate HOTP code
hotp = HOTP(secret)
code = hotp.at(counter)
# Counter is incremented after generation
```

### Code Validation

```python
# Validate with synchronization window
for offset in range(10):
    test_counter = current_counter + offset
    if hotp.verify(code, test_counter):
        # Update counter and return success
        return True
```

## Security Considerations

- **Counter synchronization**: Prevents replay attacks while handling out-of-sync scenarios
- **Sequential nature**: Each code can only be used once
- **No time dependency**: Codes remain valid until used or counter advances
- **Database persistence**: Counter state is maintained in the database

## Testing

Run the HOTP-specific tests:

```bash
python manage.py test testproject.tests.test_hotp_mail
```

## Backward Compatibility

This implementation is fully backward compatible:

- Existing TOTP methods continue to work unchanged
- New counter field has a default value of 0
- No changes to existing API endpoints or behavior

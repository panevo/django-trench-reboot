from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch, MagicMock

from trench.backends.hotp_mail import HOTPSendMailMessageDispatcher
from trench.models import MFAMethod
from trench.command.create_secret import create_secret_command


User = get_user_model()


class HOTPSendMailMessageDispatcherTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.mfa_method = MFAMethod.objects.create(
            user=self.user,
            name="hotp_email",
            secret=create_secret_command(),
            is_primary=True,
            is_active=True,
            counter=0
        )
        self.config = {
            "SOURCE_FIELD": "email",
            "EMAIL_SUBJECT": "Your HOTP verification code",
            "EMAIL_PLAIN_TEMPLATE": "trench/backends/email/code.txt",
            "EMAIL_HTML_TEMPLATE": "trench/backends/email/code.html",
        }

    def test_hotp_code_generation_increments_counter(self):
        """Test that HOTP code generation increments the counter."""
        dispatcher = HOTPSendMailMessageDispatcher(
            mfa_method=self.mfa_method, config=self.config
        )
        
        initial_counter = self.mfa_method.counter
        code = dispatcher.create_code()
        
        # Refresh from database
        self.mfa_method.refresh_from_db()
        
        # Counter should be incremented
        self.assertEqual(self.mfa_method.counter, initial_counter + 1)
        self.assertIsInstance(code, str)
        self.assertEqual(len(code), 6)  # Default HOTP code length

    def test_hotp_code_validation_with_synchronization(self):
        """Test HOTP code validation with counter synchronization."""
        dispatcher = HOTPSendMailMessageDispatcher(
            mfa_method=self.mfa_method, config=self.config
        )
        
        # Generate a code
        code = dispatcher.create_code()
        
        # Reset counter to simulate out-of-sync scenario
        self.mfa_method.counter = 0
        self.mfa_method.save()
        
        # Validation should still work due to synchronization window
        is_valid = dispatcher.validate_code(code)
        self.assertTrue(is_valid)
        
        # Counter should be updated to the correct position
        self.mfa_method.refresh_from_db()
        self.assertEqual(self.mfa_method.counter, 2)  # 1 (code position) + 1

    @patch('trench.backends.hotp_mail.send_mail')
    def test_dispatch_message_sends_email(self, mock_send_mail):
        """Test that dispatch_message sends an email with HOTP code."""
        mock_send_mail.return_value = True
        
        dispatcher = HOTPSendMailMessageDispatcher(
            mfa_method=self.mfa_method, config=self.config
        )
        
        response = dispatcher.dispatch_message()
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(response.success)
        self.assertIn("HOTP", str(response.details))

    def test_multiple_codes_are_different(self):
        """Test that consecutive HOTP codes are different."""
        dispatcher = HOTPSendMailMessageDispatcher(
            mfa_method=self.mfa_method, config=self.config
        )
        
        code1 = dispatcher.create_code()
        code2 = dispatcher.create_code()
        code3 = dispatcher.create_code()
        
        # All codes should be different
        self.assertNotEqual(code1, code2)
        self.assertNotEqual(code2, code3)
        self.assertNotEqual(code1, code3)
        
        # Counter should be at 3
        self.mfa_method.refresh_from_db()
        self.assertEqual(self.mfa_method.counter, 3)

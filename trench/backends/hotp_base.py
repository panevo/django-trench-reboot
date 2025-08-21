from django.db.models import Model

from abc import ABC, abstractmethod
from pyotp import HOTP
from typing import Any, Dict, Optional, Tuple

from trench.command.create_hotp import create_hotp_command
from trench.exceptions import MissingConfigurationError
from trench.models import MFAMethod
from trench.responses import DispatchResponse
from trench.settings import SOURCE_FIELD, VALIDITY_PERIOD, trench_settings


class AbstractHOTPMessageDispatcher(ABC):
    """Base class for HOTP-based message dispatchers."""
    
    def __init__(self, mfa_method: MFAMethod, config: Dict[str, Any]) -> None:
        self._mfa_method = mfa_method
        self._config = config
        self._to = self._get_source_field()

    def _get_source_field(self) -> Optional[str]:
        if SOURCE_FIELD in self._config:
            source = self._get_nested_attr_value(
                self._mfa_method.user, self._config[SOURCE_FIELD]
            )
            if source is None:
                raise MissingConfigurationError(
                    attribute_name=self._config[SOURCE_FIELD]
                )
            return source
        return None

    def _get_nested_attr_value(self, obj: Model, path: str) -> Optional[str]:
        objects, attr = self._parse_dotted_path(path)
        try:
            _obj = self._get_innermost_object(obj, objects)
        except AttributeError:  # pragma: no cover
            return None  # pragma: no cover
        return getattr(_obj, attr)

    @staticmethod
    def _parse_dotted_path(path: str) -> Tuple[Optional[str], str]:
        """
        Extracts attribute name from dotted path.
        """
        try:
            objects, attr = path.rsplit(".", 1)
            return objects, attr
        except ValueError:
            return None, path

    @staticmethod
    def _get_innermost_object(obj: Model, dotted_path: Optional[str] = None) -> Model:
        """
        For given object return innermost object.
        """
        if dotted_path is None:
            return obj
        for o in dotted_path.split("."):
            obj = getattr(obj, o)
        return obj  # pragma: no cover

    @abstractmethod
    def dispatch_message(self) -> DispatchResponse:
        raise NotImplementedError  # pragma: no cover

    def create_code(self) -> str:
        """Generate HOTP code and increment counter."""
        hotp = self._get_hotp()
        code = hotp.at(self._mfa_method.counter)
        # Increment counter for next use
        self._mfa_method.counter += 1
        self._mfa_method.save(update_fields=['counter'])
        return code

    def confirm_activation(self, code: str) -> None:
        pass

    def validate_confirmation_code(self, code: str) -> bool:
        return self.validate_code(code)

    def validate_code(self, code: str) -> bool:
        """Validate HOTP code only at current counter position."""
        hotp = self._get_hotp()
        
        # Only validate code at the current counter position. This is aso known as 
        # Strict HOTP validation or Synchronization-disabled HOTP validation.
        # As per OWASP testing guide, the risk of an attacker successfully guessing a code is 
        # significantly reduced if only the current code is considered valid.
        # https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/04-Authentication_Testing/11-Testing_Multi-Factor_Authentication
        if hotp.verify(code, self._mfa_method.counter):
            # Update counter for next use
            self._mfa_method.counter += 1
            self._mfa_method.save(update_fields=['counter'])
            return True
        return False

    def _get_hotp(self) -> HOTP:
        return create_hotp_command(secret=self._mfa_method.secret)

    def _get_valid_window(self) -> int:
        return self._config.get(
            VALIDITY_PERIOD, trench_settings.DEFAULT_VALIDITY_PERIOD
        )

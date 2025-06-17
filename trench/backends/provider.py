from importlib import import_module

from trench.backends.base import AbstractMessageDispatcher
from trench.models import MFAMethod
from trench.query.get_mfa_config_by_name import get_mfa_config_by_name_query
from trench.settings import HANDLER


def get_mfa_handler(mfa_method: MFAMethod) -> AbstractMessageDispatcher:
    conf = get_mfa_config_by_name_query(name=mfa_method.name)
    handler = conf[HANDLER]

    # Handler can be either a string path or already a class
    if isinstance(handler, str):
        # Import the handler class from the string path
        module_path, class_name = handler.rsplit(".", 1)
        module = import_module(module_path)
        handler_class = getattr(module, class_name)
    else:
        # Handler is already a class
        handler_class = handler

    return handler_class(mfa_method=mfa_method, config=conf)

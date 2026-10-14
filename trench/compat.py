import django
from django.db.models import Q

from typing import Dict


def check_constraint_condition(condition: Q) -> Dict[str, Q]:
    """
    Return the keyword argument for the condition of a CheckConstraint.

    Django 5.1 renamed the ``check`` argument to ``condition`` and Django 6.0
    removed ``check``, so the name depends on the Django version.
    """
    if django.VERSION >= (5, 1):
        return {"condition": condition}
    return {"check": condition}

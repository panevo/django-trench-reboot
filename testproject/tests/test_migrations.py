import pytest

from django.core.management import call_command

from io import StringIO


@pytest.mark.django_db
def test_no_missing_migrations():
    out = StringIO()
    try:
        call_command("makemigrations", "trench", check=True, dry_run=True, stdout=out)
    except SystemExit:
        pytest.fail(f"trench has model changes without a migration:\n{out.getvalue()}")

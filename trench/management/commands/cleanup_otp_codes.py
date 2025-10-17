from django.core.management.base import BaseCommand
from django.utils import timezone

from trench.models import OneTimeCode


class Command(BaseCommand):
    help = "Clean up expired one-time verification codes from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Delete codes older than this many days (default: 7)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        # Delete expired or used codes older than the cutoff date
        deleted_count, _ = OneTimeCode.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {deleted_count} old one-time codes"
            )
        )

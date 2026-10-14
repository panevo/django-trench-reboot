from django.apps import AppConfig


class TrenchConfig(AppConfig):
    name = "trench"
    # Matches the id field in the migrations, so projects that use BigAutoField
    # (the default since Django 6.0) don't get a new migration for trench.
    default_auto_field = "django.db.models.AutoField"
    verbose_name = "django-trench"

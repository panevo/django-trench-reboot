# Generated manually for HOTP support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trench', '0006_alter_mfamethod_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='mfamethod',
            name='counter',
            field=models.IntegerField(default=0, verbose_name='counter'),
        ),
    ]

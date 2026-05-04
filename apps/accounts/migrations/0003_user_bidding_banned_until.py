from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_address_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='bidding_banned_until',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Bidding suspended until this datetime. Null = no ban.',
            ),
        ),
    ]

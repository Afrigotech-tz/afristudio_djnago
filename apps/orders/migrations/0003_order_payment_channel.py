from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_add_auction_to_order_optional_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_channel',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]

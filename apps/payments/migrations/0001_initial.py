from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0002_add_auction_to_order_optional_delivery'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('bank_transfer', 'Bank Transfer (Manual)'), ('stripe', 'Stripe (International Cards)'), ('selcom', 'Selcom (Mobile Money)')], max_length=30, unique=True)),
                ('display_name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Payment Method',
                'db_table': 'payment_methods',
                'ordering': ['sort_order', 'channel'],
            },
        ),
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(max_length=30)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('currency', models.CharField(max_length=3)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('processing', 'Processing'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                        ('refunded', 'Refunded'),
                        ('cancelled', 'Cancelled'),
                    ],
                    db_index=True, default='pending', max_length=20,
                )),
                ('reference', models.CharField(blank=True, max_length=255)),
                ('proof_image', models.ImageField(blank=True, null=True, upload_to='payment_proofs/')),
                ('external_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('gateway_response', models.JSONField(blank=True, default=dict)),
                ('admin_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='orders.order')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_transactions', to=settings.AUTH_USER_MODEL)),
                ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_payments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'payment_transactions',
                'ordering': ['-created_at'],
            },
        ),
    ]

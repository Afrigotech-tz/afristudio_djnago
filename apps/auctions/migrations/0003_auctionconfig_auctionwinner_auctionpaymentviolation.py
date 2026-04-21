import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0002_allow_null_current_price'),
        ('orders', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── AuctionConfig singleton ───────────────────────────────────────────
        migrations.CreateModel(
            name='AuctionConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_mode', models.CharField(
                    choices=[
                        ('free_bid', 'Free Bid — no balance required; winner pays after auction ends'),
                        ('balance_required', 'Balance Required — must have funds; winner pays after auction ends'),
                        ('auto_deduct', 'Auto Deduct — funds held during bidding; order auto-confirmed on win'),
                    ],
                    default='auto_deduct',
                    max_length=20,
                )),
                ('payment_deadline_hours', models.PositiveIntegerField(
                    default=24,
                    help_text='Hours the winner has to complete payment before the auction is relisted.',
                )),
                ('max_violations', models.PositiveIntegerField(
                    default=3,
                    help_text='Unpaid-win violations before the user is automatically banned.',
                )),
                ('ban_duration_days', models.PositiveIntegerField(
                    default=30,
                    help_text='Ban duration in days for repeat non-payers.',
                )),
                ('relist_on_expired', models.BooleanField(
                    default=True,
                    help_text='Reset the auction and open fresh bidding if payment deadline expires.',
                )),
                ('relist_duration_hours', models.PositiveIntegerField(
                    default=48,
                    help_text='Duration (hours) of the relisted auction.',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Auction Configuration',
                'db_table': 'auction_config',
            },
        ),

        # ── AuctionWinner ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AuctionWinner',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bid_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('currency', models.CharField(max_length=3)),
                ('payment_mode', models.CharField(max_length=20)),
                ('payment_status', models.CharField(
                    choices=[
                        ('pending', 'Pending Payment'),
                        ('paid', 'Paid'),
                        ('expired', 'Expired — Auction Relisted'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('payment_deadline', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('auction', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='winner_record',
                    to='auctions.auction',
                )),
                ('order', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='auction_win',
                    to='orders.order',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='auction_wins',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'auction_winners',
                'ordering': ['-created_at'],
            },
        ),

        # ── AuctionPaymentViolation ───────────────────────────────────────────
        migrations.CreateModel(
            name='AuctionPaymentViolation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('auction_winner', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='violation',
                    to='auctions.auctionwinner',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='auction_violations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'auction_payment_violations',
                'ordering': ['-created_at'],
            },
        ),
    ]

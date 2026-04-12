import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('artworks', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Auction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
                ('start_price', models.DecimalField(decimal_places=2, max_digits=15)),
                ('reserve_price', models.DecimalField(decimal_places=2, max_digits=15, null=True, blank=True)),
                ('current_price', models.DecimalField(decimal_places=2, max_digits=15, null=True, blank=True)),
                ('bid_increment', models.DecimalField(decimal_places=2, default=1.0, max_digits=15)),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('live', 'Live'), ('ended', 'Ended'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                ('total_bids', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('artwork', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='auction', to='artworks.artwork')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_auctions', to=settings.AUTH_USER_MODEL)),
                ('winner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='won_auctions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'auctions', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Bid',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('is_winning', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('auction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bids', to='auctions.auction')),
                ('bidder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bids', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'auction_bids', 'ordering': ['-amount', '-created_at']},
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('email', 'Email'), ('sms', 'SMS')], db_index=True, max_length=10)),
                ('recipient', models.CharField(help_text='Email address or phone number', max_length=255)),
                ('subject', models.CharField(blank=True, max_length=255, null=True)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('failed', 'Failed')], db_index=True, default='sent', max_length=10)),
                ('error', models.TextField(blank=True, help_text='Error detail if delivery failed', null=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('causer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'notification_logs',
                'ordering': ['-sent_at'],
            },
        ),
    ]

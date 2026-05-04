from django.db import migrations, models


def seed_language_config(apps, schema_editor):
    LanguageConfig = apps.get_model('site_config', 'LanguageConfig')
    LanguageConfig.objects.get_or_create(
        pk=1,
        defaults={
            'enabled_languages': ['EN', 'FR', 'DE', 'ES', 'IT', 'CN', 'JP', 'AR', 'SW'],
            'default_language': 'EN',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('site_config', '0004_add_favicon_to_landing_hero'),
    ]

    operations = [
        migrations.CreateModel(
            name='LanguageConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled_languages', models.JSONField(blank=True, default=list)),
                ('default_language', models.CharField(
                    choices=[
                        ('EN', 'English'),
                        ('FR', 'French (Français)'),
                        ('DE', 'German (Deutsch)'),
                        ('ES', 'Spanish (Español)'),
                        ('IT', 'Italian (Italiano)'),
                        ('CN', 'Chinese (Mandarin / 中文)'),
                        ('JP', 'Japanese (日本語)'),
                        ('AR', 'Arabic (العربية)'),
                        ('SW', 'Swahili (Kiswahili)'),
                    ],
                    default='EN',
                    max_length=2,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'site_language_config',
                'verbose_name': 'Language Configuration',
                'verbose_name_plural': 'Language Configuration',
            },
        ),
        migrations.RunPython(seed_language_config, migrations.RunPython.noop),
    ]

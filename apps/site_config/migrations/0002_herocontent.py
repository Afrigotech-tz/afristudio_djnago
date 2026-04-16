from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_config', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeroContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tagline', models.CharField(default='Welcome to', max_length=100)),
                ('title', models.CharField(default='Afristudio', max_length=100)),
                ('subtitle', models.TextField(
                    default=(
                        'Discover the soul of Africa through exceptional artworks that '
                        'celebrate tradition, modernity, and the enduring spirit of the continent.'
                    )
                )),
                ('cta_text', models.CharField(default='Explore Gallery', max_length=50)),
                ('cta_link', models.CharField(default='/artworks', max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Hero Content',
                'verbose_name_plural': 'Hero Content',
                'db_table': 'site_hero_content',
            },
        ),
    ]

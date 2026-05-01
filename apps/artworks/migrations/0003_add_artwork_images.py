from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('artworks', '0002_add_description_to_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArtworkImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='artwork_images/')),
                ('is_primary', models.BooleanField(db_index=True, default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('artwork', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='artworks.artwork',
                )),
            ],
            options={
                'db_table': 'artwork_images',
                'ordering': ['-is_primary', 'order', 'created_at'],
            },
        ),
    ]

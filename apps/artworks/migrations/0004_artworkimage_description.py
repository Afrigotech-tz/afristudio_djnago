from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artworks', '0003_add_artwork_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='artworkimage',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
    ]

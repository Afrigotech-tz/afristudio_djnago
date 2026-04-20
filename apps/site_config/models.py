"""
site_config/models.py
Singleton models for landing page hero image, contact information,
and incoming contact messages from the public contact form.
"""

from django.db import models


# ──────────────────────────────────────────────
# Singleton base: only one row ever (pk=1)
# ──────────────────────────────────────────────
class SingletonModel(models.Model):
    """Abstract base that enforces a single database row."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # never deleted

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ──────────────────────────────────────────────
# Landing page hero image
# ──────────────────────────────────────────────
class LandingHero(SingletonModel):
    """Stores the hero/banner image and site favicon shown on the public landing page."""
    image   = models.ImageField(upload_to='landing/',  null=True, blank=True)
    favicon = models.ImageField(upload_to='favicons/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_landing_hero'
        verbose_name = 'Landing Hero'
        verbose_name_plural = 'Landing Hero'

    def __str__(self):
        return 'Landing Hero Image'


# ──────────────────────────────────────────────
# Landing page hero text content
# ──────────────────────────────────────────────
class HeroContent(SingletonModel):
    """Configurable text content for the landing page hero section."""
    tagline = models.CharField(max_length=100, default='Welcome to')
    title = models.CharField(max_length=100, default='Afristudio')
    subtitle = models.TextField(
        default=(
            'Discover the soul of Africa through exceptional artworks that '
            'celebrate tradition, modernity, and the enduring spirit of the continent.'
        )
    )
    cta_text = models.CharField(max_length=50, default='Explore Gallery')
    cta_link = models.CharField(max_length=200, default='/artworks')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_hero_content'
        verbose_name = 'Hero Content'
        verbose_name_plural = 'Hero Content'

    def __str__(self):
        return 'Landing Hero Text'


# ──────────────────────────────────────────────
# Contact information (public-facing)
# ──────────────────────────────────────────────
class ContactInfo(SingletonModel):
    """Configurable contact details displayed on the contact page."""
    email = models.EmailField(default='hello@afristudio.art')
    phone = models.CharField(max_length=30, default='+255 712 345 678')
    location = models.CharField(max_length=255, default='Dar es Salaam, Tanzania')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_contact_info'
        verbose_name = 'Contact Information'
        verbose_name_plural = 'Contact Information'

    def __str__(self):
        return 'Contact Information'


# ──────────────────────────────────────────────
# Contact messages submitted via the public form
# ──────────────────────────────────────────────
class ContactMessage(models.Model):
    STATUS_NEW = 'new'
    STATUS_READ = 'read'
    STATUS_UNREAD = 'unread'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_READ, 'Read'),
        (STATUS_UNREAD, 'Unread'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_contact_messages'
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'

    def __str__(self):
        return f'[{self.get_status_display()}] {self.subject} — {self.name}'


# ──────────────────────────────────────────────
# Artist Profile (singleton)
# ──────────────────────────────────────────────
class ArtistProfile(SingletonModel):
    name = models.CharField(max_length=255, default='Beatha Theonest')
    location = models.CharField(max_length=255, default='Arusha, Tanzania')
    photo = models.ImageField(upload_to='artist/', null=True, blank=True)
    biography = models.TextField(blank=True, default='')
    story = models.TextField(blank=True, default='')
    philosophy = models.TextField(blank=True, default='')
    statement = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_artist_profile'
        verbose_name = 'Artist Profile'
        verbose_name_plural = 'Artist Profile'

    def __str__(self):
        return f'Artist Profile — {self.name}'


# ──────────────────────────────────────────────
# Exhibitions
# ──────────────────────────────────────────────
class Exhibition(models.Model):
    date_label = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, default='')
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'site_exhibitions'
        ordering = ['order', '-created_at']
        verbose_name = 'Exhibition'
        verbose_name_plural = 'Exhibitions'

    def __str__(self):
        return f'{self.date_label} — {self.title}'

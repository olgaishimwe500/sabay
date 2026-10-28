from datetime import date

from django.conf import settings
from django.db import models

# Create your models here.
# below are the seeker and employee models.


class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# added profile fields for the seeker
class Seeker(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seeker_profile",
    )
    location = models.CharField(max_length=300, blank=True)
    photo = models.ImageField(upload_to="seekers/", blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def __str__(self):
        return f"Sekeer: {self.user}"


class Provider(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
    )
    profilePicture = models.ImageField(
        upload_to="profile_picture/",
        null=True,
        blank=True,
        verbose_name="Profile Picture",
    )
    bio = models.TextField(blank=True, verbose_name="Bio")
    specialties = models.ManyToManyField(
        Specialty, blank=True, verbose_name="Specialties"
    )
    # Could we use the django-localflavor for the state?
    # state
    # Maybe we can add something to check for a valid city
    # another model??
    city = models.CharField(max_length=50, blank=True, verbose_name="City")
    is_available = models.BooleanField(default=False, verbose_name="Is Available")

    def __str__(self):
        return f"Provider: {self.user}"


class Cert(models.Model):
    name = models.CharField(max_length=200, unique=True)

    # Allows us to change the display name on the admin panel
    class Meta:
        verbose_name = "Certification"
        verbose_name_plural = "Certifications"

    def __str__(self):
        return self.name


class ProviderCert(models.Model):
    class Meta:
        verbose_name = "Provider Specific Certification"
        verbose_name_plural = "Provider Specific Certifications"

    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="certifications"
    )
    cert = models.ForeignKey(Cert, on_delete=models.PROTECT)
    issuer = models.CharField(max_length=150, blank=False)
    document = models.FileField(upload_to="certificates/", blank=True)
    expires = models.DateField(null=True, blank=False)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f" {self.provider}"

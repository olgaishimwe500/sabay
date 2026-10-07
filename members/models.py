from django.db import models
from django.conf import settings
# Create your models here.
#below are the seeker and employee models.

class Seeker(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seeker_profile",)
    location = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"Sekeer: {self.user}"

class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile",)
    verified = models.BooleanField(default=False)
    location = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"Employee: {self.user}"


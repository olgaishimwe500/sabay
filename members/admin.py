# Register your models here.
from django.contrib import admin
from .models import Seeker, Provider

admin.site.register(Seeker)
admin.site.register(Provider)
# Register your models here.
from django.contrib import admin
from .models import Seeker, Employee

admin.site.register(Seeker)
admin.site.register(Employee)
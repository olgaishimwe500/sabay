# Register your models here.
from django.contrib import admin

from .models import Cert, Provider, ProviderCert, Seeker, Specialty

admin.site.register(Specialty)
admin.site.register(Cert)
admin.site.register(ProviderCert)
admin.site.register(Seeker)
admin.site.register(Provider)

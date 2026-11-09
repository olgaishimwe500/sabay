# Register your models here.
from django.contrib import admin

from .models import Cert, Provider, ProviderCert, Seeker, Specialty

admin.site.register(Cert)
admin.site.register(ProviderCert)
admin.site.register(Seeker)


# Helps in admin console with interactivity
@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class ProviderCertInline(admin.TabularInline):
    model = ProviderCert
    extra = 1


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "is_available")
    autocomplete_fields = ("specialties",)
    inlines = [ProviderCertInline]

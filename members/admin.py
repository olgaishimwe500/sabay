# Register your models here.
from django.contrib import admin

from .models import Cert, Provider, ProviderCert, Seeker, Specialty
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.urls import reverse

from .models import UserInvite


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

class UserInviteAdminForm(forms.ModelForm):
    class Meta:
        model = UserInvite
        fields = "__all__"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This email is already registered to an account."
            )

        if UserInvite.objects.filter(
            email__iexact=email,
            used=False,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "An active invitation already exists for this email."
            )

        return email

@admin.register(UserInvite)
class UserInviteAdmin(admin.ModelAdmin):
    form = UserInviteAdminForm
    list_display = ("email", "role", "used", "created_at")
    list_filter = ("role", "used")
    readonly_fields = ("token", "used", "created_at")

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None

        super().save_model(request, obj, form, change)

        if is_new:
            invite_path = reverse(
                "members:invite_signup",
                kwargs={"token": obj.token},
            )

            invite_url = request.build_absolute_uri(invite_path)

            send_mail(
                subject="You're invited to join Sabay",
                message=(
                    f"You've been invited to join Sabay as a "
                    f"{obj.get_role_display()}.\n\n"
                    f"Create your account here:\n{invite_url}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[obj.email],
            )

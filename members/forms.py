from django import forms
from django.core.validators import FileExtensionValidator

from .models import Provider, ProviderCert, Seeker


class SeekerProfileForm(forms.ModelForm):
    class Meta:
        model = Seeker
        fields = ["photo", "date_of_birth", "location"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}
        labels = {"location": "Address"}


class ProviderPictureForm(forms.ModelForm):
    class Meta:
        model = Provider
        fields = ["profilePicture"]
        widgets = {"profilePicture": forms.FileInput(attrs={"accept": "image/*"})}

    def clean_profilePicture(self):
        picture = self.cleaned_data.get("profilePicture")
        # Without a new upload the field falls back to the current picture,
        # so check the submitted files instead of only the cleaned value
        if not picture or self.add_prefix("profilePicture") not in self.files:
            raise forms.ValidationError("Please choose an image to upload.")
        return picture


class ProviderProfileForm(forms.ModelForm):
    """
    Fields saved by the provider profile page's "Save changes" button.
    The inputs are spread across the page (outside the <form> element),
    so each widget points back to the form with the HTML form attribute.
    """

    class Meta:
        model = Provider
        fields = ["city", "bio", "is_available", "specialties"]
        widgets = {
            "city": forms.TextInput(attrs={"form": "provider-profile-form"}),
            "bio": forms.Textarea(
                attrs={"form": "provider-profile-form", "class": "auto-grow"}
            ),
            "is_available": forms.CheckboxInput(
                attrs={"form": "provider-profile-form"}
            ),
            "specialties": forms.CheckboxSelectMultiple,
        }
        labels = {"is_available": "Accepting new jobs"}


CERT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "gif", "webp", "heic"]
CERT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


class ProviderCertForm(forms.ModelForm):
    """
    Lets a provider upload a certificate. New certificates always start
    unverified; an admin marks them verified after review.
    """

    document = forms.FileField(
        label="Photo or PDF",
        validators=[FileExtensionValidator(CERT_EXTENSIONS)],
        widget=forms.FileInput(attrs={"accept": "image/*,application/pdf"}),
    )

    class Meta:
        model = ProviderCert
        fields = ["cert", "issuer", "expires", "document"]
        widgets = {"expires": forms.DateInput(attrs={"type": "date"})}
        labels = {"cert": "Certificate", "issuer": "Issued by"}

    def __init__(self, *args, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider
        self.fields["expires"].required = True

    def clean_document(self):
        document = self.cleaned_data["document"]
        if document.size > CERT_MAX_UPLOAD_SIZE:
            raise forms.ValidationError("File is too large. The limit is 10 MB.")
        return document

    def clean_cert(self):
        cert = self.cleaned_data["cert"]
        if (
            self.provider is not None
            and self.provider.certifications.filter(cert=cert).exists()
        ):
            raise forms.ValidationError("You have already added this certificate.")
        return cert

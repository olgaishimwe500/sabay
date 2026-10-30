from django import forms

from .models import Seeker


class SeekerProfileForm(forms.ModelForm):
    class Meta:
        model = Seeker
        fields = ["photo", "date_of_birth", "location"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}
        labels = {"location": "Address"}

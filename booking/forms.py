from django import forms
from django.utils import timezone

from members.models import Provider

from .models import JobPost

##using the mockup page but could very much change
TASK_CHOICES = [
    ("Household Tasks", "Household Tasks"),
    ("Errands & Shopping", "Errands & Shopping"),
    ("Meal Preparation", "Meal Preparation"),
    ("Transportation", "Transportation"),
    ("Companionship", "Companionship"),
    ("Post-Surgery Care", "Post-Surgery Care"),
    ("Pet Care", "Pet Care"),
    ("Customize help", "customize task"),
]

DT_FORMAT = "%Y-%m-%dT%H:%M"


##actual forms that will take in all the info from seeker
class JobPostForm(forms.ModelForm):
    task_type = forms.ChoiceField(choices=TASK_CHOICES, label="type of help")
    provider = forms.ModelChoiceField(
        queryset=Provider.objects.filter(is_available=True).select_related("user"),
        required=False,
        empty_label="Any provider",
        label="Request a specific provider (optional)",
    )

    class Meta:
        model = JobPost
        fields = [
            "task_type",
            "description",
            "schedule_start",
            "schedule_end",
            "city",
            "state",
            "address",
            "zip_code",
            "provider",
        ]
        labels = {
            "schedule_start": "start",
            "schedule_end": "end",
            "city": "City",
            "state": "State",
            "address": "Street Address",
            "zip_code": "Zip code",
            "more info": "anything else we shoul know",
        }
        widgets = {
            "schedule_start": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DT_FORMAT
            ),
            "schedule_end": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DT_FORMAT
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schedule_start"].input_formats = [DT_FORMAT]
        self.fields["schedule_end"].input_formats = [DT_FORMAT]
        min_dt = timezone.localtime().strftime(DT_FORMAT)
        self.fields["schedule_start"].widget.attrs["min"] = min_dt
        self.fields["schedule_end"].widget.attrs["min"] = min_dt

    def clean_schedule_start(self):
        start = self.cleaned_data.get("schedule_start")
        if start and start < timezone.now():
            raise forms.ValidationError("The start time cannot be in the past")
        return start

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("schedule_start")
        end = cleaned.get("schedule_end")

        if start and end and end <= start:
            self.add_error("schedule_end", "The end time must be after the start time")
        return cleaned

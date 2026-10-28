from django import forms
from django.utils import timezone
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

    class Meta:
        model = JobPost
        fields = ["task_type", "description", "schedule_start", "schedule_end", "address"]
        labels = { "schedule_start": "start", "schedule_end": "end", "address": "where does the task happen", "more info": "anything else we shoul know",}
        widgets = {
            "schedule_start": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT),
            "schedule_end": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schedule_start"].input_formats = [DT_FORMAT]
        self.fields["schedule_end"].input_formats= [DT_FORMAT]

    def clean(self):
        cleaned = super().clean()
        start= cleaned.get("schedule_start")
        end=cleaned.get("schedule_end")
        

        if start and end and end <= start:
            self.add_error("schedule_end", "The end time must be after the start time")
        return cleaned
    
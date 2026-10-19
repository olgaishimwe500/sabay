from django.db import models
from members.models import Seeker, Provider
# Create your models here.
##model for job postings. different from location.seeker or location.employee'

class JobPost(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REQUESTED = "requested", "Provider requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    seeker = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name="job_posts")
    Provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="accepted_jobs")
    title = models.CharField(max_length=150, blank=True)
    task_type = models.CharField(max_length=200)
    more_info = models.TextField(blank=True)
    description = models.TextField()
    address = models.CharField(max_length=255)
    schedule_start = models.DateTimeField()
    schedule_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices =Status.choices, default=Status.OPEN)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title or self.task_type} ({self.status})"


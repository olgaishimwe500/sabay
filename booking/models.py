from django.db import models , transaction

from members.models import Provider, Seeker

# Create your models here.
##model for job postings. different from location.seeker or location.employee'


class JobPost(models.Model):
    seeker = models.ForeignKey(
        Seeker, on_delete=models.CASCADE, related_name="job_posts"
    )
    provider = models.ForeignKey(
        Provider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_jobs",
    )
    task_type = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=255)
    schedule_start = models.DateTimeField()
    schedule_end = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("open", "Open"),
            ("accepted", "Accepted"),
            ("declined", "Declined"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="open",
    )
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class JobReq(models.Model):
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("declined", "Declined"),
        ],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    """
    Allows seekers to approve a request
    """
    def approve(self):
        with transaction.atomic():
            self.status = "approved"
            self.save()

            job = self.job
            job.provider = self.provider
            job.status = "accepted"
            job.save()

            type(self).objects.filter(job=job).exclude(pk=self.pk).update(status="declined")
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "provider"], name="one_application_per_provider")
        ]


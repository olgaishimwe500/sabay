from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone

from members.models import Provider, Seeker
from members.states import STATES

# Create your models here.
##model for job postings. different from location.seeker or location.employee'


class JobPostQuerySet(models.QuerySet):
    def expire_past_due(self, now=None):
        """
        Marks open jobs as expired once their start time has passed without
        a provider being accepted. Returns the number of jobs expired.
        """
        now = now or timezone.now()
        return self.filter(status="open", schedule_start__lte=now).update(
            status="expired"
        )


class JobPost(models.Model):
    zip_validator = RegexValidator(
        regex=r"^\d{5}(?:-\d{4})?$",
        message="Enter a valid US ZIP code (e.g., 12345 or 12345-6789).",
    )

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

    city = models.CharField(max_length=50, blank=True, verbose_name="City")
    state = models.CharField(
        max_length=2, choices=STATES, blank=True, verbose_name="State"
    )
    task_type = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=5, validators=[zip_validator])
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
            ("expired", "Expired"),
        ],
        default="open",
    )
    # Both sides must confirm before the job counts as completed
    seeker_completed = models.BooleanField(default=False)
    provider_completed = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = JobPostQuerySet.as_manager()

    def has_started(self, now=None):
        return self.schedule_start <= (now or timezone.now())

    def mark_complete(self, by):
        """
        Records that the seeker or provider ("seeker"/"provider") says the job
        is done. The job only becomes completed once both have confirmed.
        """
        if by == "seeker":
            self.seeker_completed = True
        elif by == "provider":
            self.provider_completed = True
        else:
            raise ValueError(f"Unknown party: {by!r}")
        if self.seeker_completed and self.provider_completed:
            self.status = "completed"
        self.save(update_fields=["seeker_completed", "provider_completed", "status"])


class JobReq(models.Model):
    job = models.ForeignKey(
        JobPost, on_delete=models.CASCADE, related_name="applications"
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="applications"
    )
    dismissed = models.BooleanField(default=False)
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

            type(self).objects.filter(job=job).exclude(pk=self.pk).update(
                status="declined"
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "provider"], name="one_application_per_provider"
            )
        ]

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Provider, Seeker

from .models import JobPost, JobReq

User = get_user_model()


class JobBoardTests(TestCase):
    def setUp(self):
        self.url = reverse("booking:job_list")
        provider_user = User.objects.create_user(username="pat", password="password")
        self.provider = Provider.objects.create(user=provider_user)
        self.client.force_login(provider_user)

        seeker_user = User.objects.create_user(
            username="sue", password="password", first_name="Sue", last_name="Lee"
        )
        self.seeker = Seeker.objects.create(user=seeker_user)
        start = timezone.now() + timedelta(days=2)
        self.older = self.make_job("Meal prep", start)
        self.newer = self.make_job("Companion care", start)

    def make_job(self, task_type, start):
        return JobPost.objects.create(
            seeker=self.seeker,
            task_type=task_type,
            description="Details",
            address="123 Main St",
            schedule_start=start,
            schedule_end=start + timedelta(hours=3),
        )

    def test_seeker_is_redirected(self):
        self.client.force_login(self.seeker.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("members:seeker_dashboard"))

    def test_newest_job_is_selected_by_default(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["selected"], self.newer)
        self.assertFalse(response.context["has_selection"])

    def test_job_query_param_selects_job(self):
        response = self.client.get(self.url, {"job": self.older.pk})
        self.assertEqual(response.context["selected"], self.older)
        self.assertTrue(response.context["has_selection"])

    def test_unknown_job_falls_back_to_newest(self):
        response = self.client.get(self.url, {"job": "999999"})
        self.assertEqual(response.context["selected"], self.newer)
        self.assertFalse(response.context["has_selection"])

    def test_address_is_not_shown(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "123 Main St")
        self.assertContains(response, "Shared after confirmation")

    def test_requested_job_shows_status_instead_of_button(self):
        JobReq.objects.create(job=self.newer, provider=self.provider)
        response = self.client.get(self.url)
        self.assertEqual(response.context["selected"].my_status, "pending")
        self.assertContains(response, "Requested &middot; waiting on seeker")
        self.assertNotContains(response, "Request this job")

    def test_request_from_board_returns_to_board(self):
        next_url = f"{self.url}?job={self.older.pk}"
        response = self.client.post(
            reverse("members:job_request", args=[self.older.pk]), {"next": next_url}
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertTrue(
            JobReq.objects.filter(job=self.older, provider=self.provider).exists()
        )

    def test_request_ignores_external_next(self):
        response = self.client.post(
            reverse("members:job_request", args=[self.older.pk]),
            {"next": "https://evil.example.com/"},
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )

    def test_expired_jobs_are_hidden(self):
        self.older.status = "expired"
        self.older.save()
        response = self.client.get(self.url)
        self.assertNotIn(self.older, response.context["jobs"])
        self.assertIn(self.newer, response.context["jobs"])

    def test_past_open_jobs_are_expired_and_hidden(self):
        past = timezone.now() - timedelta(hours=1)
        stale = self.make_job("Yesterday's errand", past)
        response = self.client.get(self.url)
        self.assertNotIn(stale, response.context["jobs"])

    def test_jobs_accepted_by_other_providers_are_hidden(self):
        other_user = User.objects.create_user(username="john", password="password")
        other = Provider.objects.create(user=other_user)
        JobReq.objects.create(job=self.older, provider=other).approve()
        response = self.client.get(self.url)
        self.assertNotIn(self.older, response.context["jobs"])
        self.assertIn(self.newer, response.context["jobs"])

    def test_jobs_accepted_by_this_provider_are_shown(self):
        JobReq.objects.create(job=self.older, provider=self.provider).approve()
        response = self.client.get(self.url, {"job": self.older.pk})
        self.assertIn(self.older, response.context["jobs"])
        self.assertContains(response, "You're booked for this job")

    def test_other_statuses_are_hidden(self):
        for status in ("declined", "completed", "cancelled", "not_selected"):
            self.older.status = status
            self.older.save()
            response = self.client.get(self.url)
            self.assertNotIn(self.older, response.context["jobs"], status)

    def test_board_has_no_post_a_job_link(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("booking:post_job"))

    def test_provider_cannot_open_post_job(self):
        response = self.client.get(reverse("booking:post_job"))
        self.assertRedirects(response, self.url)

    def test_provider_cannot_submit_job(self):
        start = timezone.now() + timedelta(days=3)
        response = self.client.post(
            reverse("booking:post_job"),
            {
                "task_type": "Sneaky",
                "description": "x",
                "address": "1 Main St",
                "schedule_start": start,
                "schedule_end": start + timedelta(hours=1),
            },
        )
        self.assertRedirects(response, self.url)
        self.assertFalse(JobPost.objects.filter(task_type="Sneaky").exists())
        self.assertFalse(Seeker.objects.filter(user=self.provider.user).exists())

    def test_seeker_can_open_post_job(self):
        self.client.force_login(self.seeker.user)
        response = self.client.get(reverse("booking:post_job"))
        self.assertEqual(response.status_code, 200)

    def test_empty_board(self):
        JobPost.objects.all().delete()
        response = self.client.get(self.url)
        self.assertIsNone(response.context["selected"])
        self.assertContains(response, "No jobs posted yet.")

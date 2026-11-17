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


class SeekerEditCancelTests(TestCase):
    def setUp(self):
        self.seeker = Seeker.objects.create(
            user=User.objects.create_user(username="ana", password="password")
        )
        self.other_seeker = Seeker.objects.create(
            user=User.objects.create_user(username="bea", password="password")
        )
        self.provider = Provider.objects.create(
            user=User.objects.create_user(username="john", password="password")
        )
        self.client.force_login(self.seeker.user)

    def make_job(self, seeker=None, start=None, **overrides):
        start = start or timezone.now() + timedelta(days=2)
        fields = {
            "seeker": seeker or self.seeker,
            "task_type": "Pet Care",
            "description": "Walk the dog",
            "address": "1 Main St",
            "zip_code": "97201",
            "schedule_start": start,
            "schedule_end": start + timedelta(hours=1),
        }
        fields.update(overrides)
        return JobPost.objects.create(**fields)

    def edit_data(self, job, **overrides):
        start = timezone.localtime(job.schedule_start) + timedelta(days=1)
        data = {
            "task_type": "Meal Preparation",
            "description": "Cook dinner",
            "address": job.address,
            "zip_code": job.zip_code,
            "schedule_start": start.strftime("%Y-%m-%dT%H:%M"),
            "schedule_end": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        }
        data.update(overrides)
        return data

    def test_dashboard_shows_edit_and_cancel_for_open_job(self):
        job = self.make_job()
        response = self.client.get(reverse("members:seeker_dashboard"))
        self.assertContains(response, reverse("booking:edit_job", args=[job.pk]))
        self.assertContains(response, reverse("booking:cancel_job", args=[job.pk]))

    def test_dashboard_shows_cancel_but_not_edit_for_upcoming_job(self):
        job = self.make_job(provider=self.provider, status="accepted")
        response = self.client.get(reverse("members:seeker_dashboard"))
        self.assertContains(response, reverse("booking:cancel_job", args=[job.pk]))
        self.assertNotContains(response, reverse("booking:edit_job", args=[job.pk]))

    def test_edit_page_is_prefilled(self):
        job = self.make_job()
        response = self.client.get(reverse("booking:edit_job", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit job")
        self.assertContains(response, "Walk the dog")

    def test_edit_updates_job(self):
        job = self.make_job()
        response = self.client.post(
            reverse("booking:edit_job", args=[job.pk]), self.edit_data(job)
        )
        self.assertRedirects(response, reverse("members:seeker_dashboard"))
        job.refresh_from_db()
        self.assertEqual(job.task_type, "Meal Preparation")
        self.assertEqual(job.description, "Cook dinner")
        self.assertEqual(job.seeker, self.seeker)

    def test_edit_rejects_invalid_data(self):
        job = self.make_job()
        data = self.edit_data(job, schedule_end=self.edit_data(job)["schedule_start"])
        response = self.client.post(reverse("booking:edit_job", args=[job.pk]), data)
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.task_type, "Pet Care")

    def test_cannot_edit_other_seekers_job(self):
        job = self.make_job(seeker=self.other_seeker)
        response = self.client.post(
            reverse("booking:edit_job", args=[job.pk]), self.edit_data(job)
        )
        self.assertEqual(response.status_code, 404)
        job.refresh_from_db()
        self.assertEqual(job.task_type, "Pet Care")

    def test_cannot_edit_accepted_job(self):
        job = self.make_job(provider=self.provider, status="accepted")
        response = self.client.get(reverse("booking:edit_job", args=[job.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cancel_open_job_declines_pending_requests(self):
        job = self.make_job()
        req = JobReq.objects.create(job=job, provider=self.provider)
        response = self.client.post(reverse("booking:cancel_job", args=[job.pk]))
        self.assertRedirects(response, reverse("members:seeker_dashboard"))
        job.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(req.status, "declined")

    def test_cancel_accepted_job(self):
        job = self.make_job(provider=self.provider, status="accepted")
        self.client.post(reverse("booking:cancel_job", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")

    def test_cancelled_job_leaves_dashboard(self):
        job = self.make_job()
        self.client.post(reverse("booking:cancel_job", args=[job.pk]))
        response = self.client.get(reverse("members:seeker_dashboard"))
        self.assertNotContains(response, reverse("booking:edit_job", args=[job.pk]))

    def test_cancel_requires_post(self):
        job = self.make_job()
        response = self.client.get(reverse("booking:cancel_job", args=[job.pk]))
        self.assertEqual(response.status_code, 405)
        job.refresh_from_db()
        self.assertEqual(job.status, "open")

    def test_cannot_cancel_other_seekers_job(self):
        job = self.make_job(seeker=self.other_seeker)
        response = self.client.post(reverse("booking:cancel_job", args=[job.pk]))
        self.assertEqual(response.status_code, 404)
        job.refresh_from_db()
        self.assertEqual(job.status, "open")

    def test_cannot_cancel_started_job(self):
        job = self.make_job(
            provider=self.provider,
            status="accepted",
            start=timezone.now() - timedelta(hours=1),
        )
        response = self.client.post(reverse("booking:cancel_job", args=[job.pk]))
        self.assertEqual(response.status_code, 404)
        job.refresh_from_db()
        self.assertEqual(job.status, "accepted")

# Create your tests here.
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from .models import UserInvite


from booking.models import JobPost, JobReq

from .models import Cert, Provider, ProviderCert, Seeker, Specialty

User = get_user_model()


# Unit test for the Provider, Cert, Specialty, and ProviderCert models
class ProviderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="password")
        self.provider = Provider.objects.create(
            user=self.user, city="Salem", bio="work well with dogs"
        )

    def test_username_exists(self):
        self.assertIn("bob", str(self.provider))

    def test_bio_added(self):
        self.assertIn("work well with dogs", str(self.provider.bio))

    def test_city_added(self):
        self.assertIn("Salem", str(self.provider.city))

    def test_provider_specialties_added(self):
        cooking = Specialty.objects.create(name="Cooking")
        elderCare = Specialty.objects.create(name="Elder Care")

        self.provider.specialties.add(cooking, elderCare)
        names = set(self.provider.specialties.values_list("name", flat=True))
        self.assertEqual(names, {"Cooking", "Elder Care"})


class CertificateTests(TestCase):
    def setUp(self):
        self.bob = User.objects.create_user(username="bob", password="password")
        self.provider = Provider.objects.create(user=self.bob)
        self.cpr = Cert.objects.create(name="CPR")

    def test_cert_is_linked(self):
        ProviderCert.objects.create(provider=self.provider, cert=self.cpr)
        self.assertEqual(self.provider.certifications.count(), 1)

    def test_cert_is_unique(self):
        with self.assertRaises(IntegrityError):
            Cert.objects.create(name="CPR")

    def test_multiple_providers_share_cert(self):
        john = User.objects.create_user(username="john", password="password")
        other_provider = Provider.objects.create(user=john)

        ProviderCert.objects.create(
            provider=self.provider, cert=self.cpr, issuer="American Red Cross"
        )
        ProviderCert.objects.create(
            provider=other_provider, cert=self.cpr, issuer="American Red Cross"
        )

        self.assertEqual(ProviderCert.objects.filter(cert=self.cpr).count(), 2)


# GET method test for autofill function
class AutofillCityTests(TestCase):
    def test_get_city_code(self):
        response = self.client.get(reverse("members:city_suggestions"), {"page": 1})
        self.assertEqual(response.status_code, 200)


class JobResponseTest(TestCase):
    def setUp(self):
        self.john = User.objects.create_user(username="john", password="password")
        self.provider = Provider.objects.create(user=self.john)

        self.ana = User.objects.create_user(username="ana", password="password")
        self.seeker = Seeker.objects.create(user=self.ana)

        self.job = self.make_job()
        self.url = reverse("members:job_response", args=[self.job.id])

    def make_job(self, **overrides):
        start = timezone.now() + timedelta(days=1)
        data = {
            "seeker": self.seeker,
            "provider": self.provider,
            "status": "open",
            "task_type": "Cleaning",
            "address": "123 Test St",
            "schedule_start": start,
            "schedule_end": start + timedelta(hours=2),
        }
        data.update(overrides)
        return JobPost.objects.create(**data)

    def test_status_to_accepted(self):
        self.client.login(username="john", password="password")
        response = self.client.post(self.url, {"action": "accept"})

        self.assertEqual(response.status_code, 302)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "accepted")

    def test_status_to_declined(self):
        self.client.login(username="john", password="password")

        self.client.post(self.url, {"action": "decline"})

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "declined")


class CompleteJobTest(TestCase):
    def setUp(self):
        self.john = User.objects.create_user(username="john", password="password")
        self.provider = Provider.objects.create(user=self.john)

        self.ana = User.objects.create_user(username="ana", password="password")
        self.seeker = Seeker.objects.create(user=self.ana)

        start = timezone.now() + timedelta(days=1)
        self.job = JobPost.objects.create(
            seeker=self.seeker,
            provider=self.provider,
            status="accepted",
            task_type="Cleaning",
            address="123 Test St",
            schedule_start=start,
            schedule_end=start + timedelta(hours=2),
        )
        self.url = reverse("members:complete_job", args=[self.job.id])

    def test_dashboard_shows_complete_button(self):
        self.client.login(username="john", password="password")
        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, self.url)

    def test_complete_sets_status(self):
        self.client.login(username="john", password="password")
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("dashboard"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "completed")

    def test_get_not_allowed(self):
        self.client.login(username="john", password="password")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_other_provider_cannot_complete(self):
        toby = User.objects.create_user(username="toby", password="password")
        Provider.objects.create(user=toby)
        self.client.login(username="toby", password="password")
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "accepted")

    def test_open_job_cannot_be_completed(self):
        self.job.status = "open"
        self.job.save()
        self.client.login(username="john", password="password")
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)


class JobRequestButtonTest(TestCase):
    def setUp(self):
        self.john = User.objects.create_user(username="john", password="password")
        self.provider = Provider.objects.create(user=self.john)

        self.ana = User.objects.create_user(username="ana", password="password")
        self.seeker = Seeker.objects.create(user=self.ana)

        start = timezone.now() + timedelta(days=1)
        self.job = JobPost.objects.create(
            seeker=self.seeker,
            status="open",
            task_type="Cleaning",
            address="123 Test St",
            schedule_start=start,
            schedule_end=start + timedelta(hours=2),
        )
        self.url = reverse("members:job_request", args=[self.job.id])

    def test_request_creates_job_req(self):
        self.client.login(username="john", password="password")
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JobReq.objects.filter(job=self.job, provider=self.provider).exists()
        )

    def test_request_twice_only_creates_one(self):
        self.client.login(username="john", password="password")
        self.client.post(self.url)
        self.client.post(self.url)

        self.assertEqual(
            JobReq.objects.filter(job=self.job, provider=self.provider).count(), 1
        )

    def test_approved_job_listed_once_in_upcoming(self):
        toby = User.objects.create_user(username="toby", password="password")
        other = Provider.objects.create(user=toby)
        JobReq.objects.create(job=self.job, provider=other)
        JobReq.objects.create(job=self.job, provider=self.provider).approve()

        self.client.login(username="john", password="password")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(list(response.context["upcoming_jobs"]), [self.job])


class LoginViewTests(TestCase):
    def setUp(self):
        self.url = reverse("members:login")

    def test_staff_user_is_rejected(self):
        User.objects.create_user(username="staff", password="password", is_staff=True)
        response = self.client.post(
            self.url, {"username": "staff", "password": "password"}
        )
        self.assertEqual(response.status_code, 403)

    def test_superuser_is_rejected(self):
        User.objects.create_superuser(username="admin", password="password")
        response = self.client.post(
            self.url, {"username": "admin", "password": "password"}
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_password_for_staff_shows_generic_error(self):
        User.objects.create_user(username="staff", password="password", is_staff=True)
        response = self.client.post(self.url, {"username": "staff", "password": "nope"})
        self.assertEqual(response.status_code, 200)

    def test_provider_logs_in_and_goes_to_dashboard(self):
        user = User.objects.create_user(username="bob", password="password")
        Provider.objects.create(user=user)
        response = self.client.post(
            self.url, {"username": "bob", "password": "password"}
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_seeker_logs_in_and_goes_home(self):
        user = User.objects.create_user(username="sue", password="password")
        Seeker.objects.create(user=user)
        response = self.client.post(
            self.url, {"username": "sue", "password": "password"}
        )
        self.assertRedirects(response, reverse("members:seeker_dashboard"), fetch_redirect_response=False)


class SignupTests(TestCase):
    def test_public_signup_displays_contact_admin_message(self):
        response = self.client.get(reverse("members:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please contact an admin to sign up.",
        )

    def test_public_signup_cannot_create_user(self):
        response = self.client.post(
            reverse("members:signup"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPassword123!",
                "confirm_password": "TestPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="testuser").exists()
        )


class UserInviteTests(TestCase):
    def setUp(self):
        self.invite = UserInvite.objects.create(
            email="caretaker@example.com",
            role=UserInvite.Role.CARETAKER,
        )

        self.invite_url = reverse(
            "members:invite_signup",
            args=[self.invite.token],
        )

    def signup_with_invite(self, username="testuser"):
        return self.client.post(
            self.invite_url,
            {
                "username": username,
                "password": "TestPassword123!",
                "confirm_password": "TestPassword123!",
            },
        )

    def test_valid_invite_displays_signup_page(self):
        response = self.client.get(self.invite_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "caretaker@example.com")

    def test_invalid_invite_displays_invalid_page(self):
        response = self.client.get(
            reverse(
                "members:invite_signup",
                args=["fake-token"],
            )
        )

        self.assertContains(response, "Invalid Invitation")

    def test_caretaker_signup_creates_user(self):
        response = self.signup_with_invite("caretaker1")

        self.assertTrue(
            User.objects.filter(
                username="caretaker1",
                email="caretaker@example.com",
            ).exists()
        )

        self.assertRedirects(response, reverse("members:login"))

    def test_caretaker_signup_assigns_caretaker_group(self):
        self.signup_with_invite("caretaker1")

        user = User.objects.get(username="caretaker1")

        self.assertTrue(
            user.groups.filter(name="Caretaker").exists()
        )
        self.assertFalse(
            user.groups.filter(name="Careseeker").exists()
        )

    def test_careseeker_signup_assigns_careseeker_group(self):
        self.invite.role = UserInvite.Role.CARESEEKER
        self.invite.save(update_fields=["role"])

        response = self.signup_with_invite("careseeker1")

        user = User.objects.get(username="careseeker1")

        self.assertTrue(
            user.groups.filter(name="Careseeker").exists()
        )
        self.assertFalse(
            user.groups.filter(name="Caretaker").exists()
        )
        self.assertRedirects(response, reverse("members:login"))

    def test_signup_marks_invite_used(self):
        self.signup_with_invite("caretaker1")

        self.invite.refresh_from_db()

        self.assertTrue(self.invite.used)

    def test_used_invite_cannot_be_reused(self):
        self.invite.used = True
        self.invite.save(update_fields=["used"])

        response = self.client.get(self.invite_url)

        self.assertContains(response, "Invalid Invitation")

    def test_invite_cannot_be_used_twice(self):
        self.signup_with_invite("firstuser")

        response = self.signup_with_invite("seconduser")

        self.assertContains(response, "Invalid Invitation")
        self.assertFalse(
            User.objects.filter(username="seconduser").exists()
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class UserInviteAdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.client.force_login(self.admin)

    def test_admin_rejects_duplicate_active_invite(self):
        UserInvite.objects.create(
            email="duplicate@example.com",
            role=UserInvite.Role.CARETAKER,
        )

        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "DUPLICATE@example.com",
                "role": UserInvite.Role.CARESEEKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "An active invitation already exists for this email.",
        )
        self.assertEqual(
            UserInvite.objects.filter(email__iexact="duplicate@example.com").count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_rejects_existing_user_email(self):
        User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "EXISTING@example.com",
                "role": UserInvite.Role.CARETAKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This email is already registered to an account.",
        )
        self.assertFalse(
            UserInvite.objects.filter(email__iexact="existing@example.com").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_creating_caretaker_invite_sends_email(self):
        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "newcaretaker@example.com",
                "role": UserInvite.Role.CARETAKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        invite = UserInvite.objects.get(
            email="newcaretaker@example.com"
        )

        self.assertEqual(invite.role, UserInvite.Role.CARETAKER)
        self.assertFalse(invite.used)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["newcaretaker@example.com"],
        )

        invite_url = reverse(
            "members:invite_signup",
            args=[invite.token],
        )

        self.assertIn(invite_url, mail.outbox[0].body)
        self.assertIn("Caretaker", mail.outbox[0].body)

    def test_admin_creating_careseeker_invite_sends_email(self):
        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "newcareseeker@example.com",
                "role": UserInvite.Role.CARESEEKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        invite = UserInvite.objects.get(
            email="newcareseeker@example.com"
        )

        self.assertEqual(invite.role, UserInvite.Role.CARESEEKER)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["newcareseeker@example.com"],
        )
        self.assertIn("Careseeker", mail.outbox[0].body)

# Create your tests here.
import shutil
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)


# Smallest valid GIF (1x1 pixel) so ImageField validation passes in tests
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def make_gif(name="photo.gif"):
    return SimpleUploadedFile(name, TINY_GIF, content_type="image/gif")


def make_pdf(name="cert.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


class ProviderProfileTestBase(TestCase):
    """
    Shared setup for the provider profile tests. Uploaded files are written
    to a temporary MEDIA_ROOT so the real media/ folder is never touched.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="bob",
            password="password",
            first_name="Bob",
            last_name="Smith",
        )
        self.provider = Provider.objects.create(
            user=self.user, city="Salem", bio="Good with dogs"
        )
        self.client.login(username="bob", password="password")


class ProviderProfilePageTests(ProviderProfileTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("members:provider_profile_edit")

    def test_anonymous_user_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('members:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_seeker_redirected_home(self):
        seeker_user = User.objects.create_user(username="sue", password="password")
        Seeker.objects.create(user=seeker_user)
        self.client.login(username="sue", password="password")

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_provider_sees_profile_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "providers/profile.html")
        self.assertEqual(response.context["provider"], self.provider)
        self.assertContains(response, "Edit profile")

    def test_names_shown_read_only(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'value="Bob" readonly', html=False)
        self.assertContains(response, 'value="Smith" readonly', html=False)

    def test_city_and_bio_prefilled(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'value="Salem"')
        self.assertContains(response, "Good with dogs</textarea>")

    def test_initials_shown_without_picture(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<span class="profile-initials"')
        self.assertContains(response, "BS")
        # No remove button when there is nothing to remove
        self.assertNotContains(response, reverse("members:remove_profile_picture"))

    def test_picture_and_remove_button_shown_with_picture(self):
        self.provider.profilePicture = make_gif()
        self.provider.save()

        response = self.client.get(self.url)
        self.assertContains(response, self.provider.profilePicture.url)
        self.assertContains(response, "Bob Smith's profile picture")
        self.assertContains(response, reverse("members:remove_profile_picture"))

    def test_specialties_listed_and_checked(self):
        cooking = Specialty.objects.create(name="Cooking")
        Specialty.objects.create(name="Elder Care")
        self.provider.specialties.add(cooking)

        response = self.client.get(self.url)
        self.assertContains(response, "Cooking")
        self.assertContains(response, "Elder Care")
        form = response.context["profile_form"]
        self.assertEqual(list(form.initial["specialties"]), [cooking])

    def test_empty_certificates_message(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No certificates added yet.")

    def test_certificates_listed_with_status(self):
        cpr = Cert.objects.create(name="CPR")
        first_aid = Cert.objects.create(name="First Aid")
        ProviderCert.objects.create(
            provider=self.provider,
            cert=cpr,
            issuer="American Red Cross",
            expires=date(2027, 5, 1),
            is_verified=True,
        )
        ProviderCert.objects.create(
            provider=self.provider, cert=first_aid, issuer="County"
        )

        response = self.client.get(self.url)
        self.assertNotContains(response, "No certificates added yet.")
        self.assertContains(response, "American Red Cross")
        self.assertContains(response, "expires May 2027")
        self.assertContains(response, '<span class="cert-status verified">')
        self.assertContains(response, '<span class="cert-status pending">')
        names = [pc.cert.name for pc in response.context["certifications"]]
        self.assertEqual(names, ["CPR", "First Aid"])

    def test_other_providers_certificates_not_shown(self):
        other_user = User.objects.create_user(username="ann", password="password")
        other = Provider.objects.create(user=other_user)
        cpr = Cert.objects.create(name="CPR")
        ProviderCert.objects.create(provider=other, cert=cpr, issuer="Somewhere")

        response = self.client.get(self.url)
        self.assertEqual(list(response.context["certifications"]), [])

    def test_add_certificate_closed_without_errors(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<details class="add-certificate">')

    def test_post_only_views_reject_get(self):
        for name in [
            "members:add_profile_picture",
            "members:remove_profile_picture",
            "members:update_provider_profile",
            "members:add_certificate",
        ]:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 405)

    def test_dashboard_profile_card_links_to_edit_page(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, f'href="{self.url}"')


class ProfilePictureViewTests(ProviderProfileTestBase):
    def setUp(self):
        super().setUp()
        self.upload_url = reverse("members:add_profile_picture")
        self.remove_url = reverse("members:remove_profile_picture")
        self.profile_url = reverse("members:provider_profile_edit")

    def test_upload_saves_picture(self):
        response = self.client.post(self.upload_url, {"profilePicture": make_gif()})

        self.assertRedirects(response, self.profile_url, fetch_redirect_response=False)
        self.provider.refresh_from_db()
        self.assertTrue(
            self.provider.profilePicture.name.startswith("profile_picture/")
        )
        self.assertTrue(
            self.provider.profilePicture.storage.exists(
                self.provider.profilePicture.name
            )
        )

    def test_upload_replaces_and_deletes_old_picture(self):
        self.client.post(self.upload_url, {"profilePicture": make_gif("old.gif")})
        self.provider.refresh_from_db()
        old_name = self.provider.profilePicture.name
        storage = self.provider.profilePicture.storage

        self.client.post(self.upload_url, {"profilePicture": make_gif("new.gif")})
        self.provider.refresh_from_db()

        self.assertNotEqual(self.provider.profilePicture.name, old_name)
        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(self.provider.profilePicture.name))

    def test_upload_without_file_shows_error(self):
        response = self.client.post(self.upload_url, {})

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "providers/profile.html")
        self.assertContains(
            response, "Please choose an image to upload.", status_code=400
        )

    def test_upload_without_file_shows_error_when_picture_exists(self):
        self.client.post(self.upload_url, {"profilePicture": make_gif()})
        self.provider.refresh_from_db()
        current = self.provider.profilePicture.name

        response = self.client.post(self.upload_url, {})

        self.assertContains(
            response, "Please choose an image to upload.", status_code=400
        )
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.profilePicture.name, current)
        self.assertTrue(self.provider.profilePicture.storage.exists(current))

    def test_upload_non_image_rejected(self):
        bad = SimpleUploadedFile("notes.gif", b"not an image", content_type="image/gif")
        response = self.client.post(self.upload_url, {"profilePicture": bad})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["picture_form"].errors)
        self.provider.refresh_from_db()
        self.assertFalse(self.provider.profilePicture)

    def test_failed_upload_keeps_current_picture(self):
        self.client.post(self.upload_url, {"profilePicture": make_gif()})
        self.provider.refresh_from_db()
        current = self.provider.profilePicture.name

        bad = SimpleUploadedFile("bad.gif", b"not an image", content_type="image/gif")
        response = self.client.post(self.upload_url, {"profilePicture": bad})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context["provider"].profilePicture.name, current)
        self.assertTrue(self.provider.profilePicture.storage.exists(current))
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.profilePicture.name, current)

    def test_remove_deletes_picture_and_file(self):
        self.client.post(self.upload_url, {"profilePicture": make_gif()})
        self.provider.refresh_from_db()
        name = self.provider.profilePicture.name
        storage = self.provider.profilePicture.storage

        response = self.client.post(self.remove_url)

        self.assertRedirects(response, self.profile_url, fetch_redirect_response=False)
        self.provider.refresh_from_db()
        self.assertFalse(self.provider.profilePicture)
        self.assertFalse(storage.exists(name))

    def test_remove_without_picture_is_harmless(self):
        response = self.client.post(self.remove_url)
        self.assertRedirects(response, self.profile_url, fetch_redirect_response=False)

    def test_seeker_cannot_upload(self):
        seeker_user = User.objects.create_user(username="sue", password="password")
        Seeker.objects.create(user=seeker_user)
        self.client.login(username="sue", password="password")

        response = self.client.post(self.upload_url, {"profilePicture": make_gif()})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_anonymous_cannot_upload(self):
        self.client.logout()
        response = self.client.post(self.upload_url, {"profilePicture": make_gif()})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("members:login"), response["Location"])


class UpdateProviderProfileViewTests(ProviderProfileTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("members:update_provider_profile")
        self.cooking = Specialty.objects.create(name="Cooking")
        self.elder_care = Specialty.objects.create(name="Elder Care")

    def test_valid_post_updates_profile(self):
        response = self.client.post(
            self.url,
            {
                "city": "Portland",
                "bio": "Ten years of experience",
                "is_available": "on",
                "specialties": [self.cooking.pk, self.elder_care.pk],
            },
        )

        self.assertRedirects(
            response,
            reverse("members:provider_profile_edit"),
            fetch_redirect_response=False,
        )
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.city, "Portland")
        self.assertEqual(self.provider.bio, "Ten years of experience")
        self.assertTrue(self.provider.is_available)
        self.assertEqual(
            set(self.provider.specialties.all()), {self.cooking, self.elder_care}
        )

    def test_unchecked_fields_are_cleared(self):
        self.provider.is_available = True
        self.provider.save()
        self.provider.specialties.add(self.cooking)

        self.client.post(self.url, {"city": "Salem", "bio": ""})

        self.provider.refresh_from_db()
        self.assertFalse(self.provider.is_available)
        self.assertEqual(self.provider.specialties.count(), 0)
        self.assertEqual(self.provider.bio, "")

    def test_invalid_specialty_shows_error(self):
        response = self.client.post(self.url, {"city": "Salem", "specialties": [9999]})

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "providers/profile.html")
        self.assertIn("specialties", response.context["profile_form"].errors)

    def test_city_too_long_rejected_and_not_saved(self):
        response = self.client.post(self.url, {"city": "x" * 51, "bio": "new bio"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("city", response.context["profile_form"].errors)
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.city, "Salem")
        self.assertEqual(self.provider.bio, "Good with dogs")

    def test_seeker_cannot_update(self):
        seeker_user = User.objects.create_user(username="sue", password="password")
        Seeker.objects.create(user=seeker_user)
        self.client.login(username="sue", password="password")

        response = self.client.post(self.url, {"city": "Portland"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)


class AddCertificateViewTests(ProviderProfileTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("members:add_certificate")
        self.cpr = Cert.objects.create(name="CPR")

    def cert_data(self, **overrides):
        data = {
            "cert": self.cpr.pk,
            "issuer": "American Red Cross",
            "expires": "2027-05-01",
            "document": make_pdf(),
        }
        data.update(overrides)
        return data

    def test_valid_upload_creates_unverified_cert(self):
        response = self.client.post(self.url, self.cert_data(is_verified="on"))

        self.assertRedirects(
            response,
            reverse("members:provider_profile_edit"),
            fetch_redirect_response=False,
        )
        provider_cert = ProviderCert.objects.get(provider=self.provider)
        self.assertEqual(provider_cert.cert, self.cpr)
        self.assertEqual(provider_cert.issuer, "American Red Cross")
        self.assertEqual(provider_cert.expires, date(2027, 5, 1))
        self.assertFalse(provider_cert.is_verified)
        self.assertTrue(provider_cert.document.name.startswith("certificates/"))

    def test_image_upload_allowed(self):
        response = self.client.post(
            self.url, self.cert_data(document=make_gif("cert.gif"))
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.provider.certifications.count(), 1)

    def test_disallowed_extension_rejected(self):
        bad = SimpleUploadedFile("cert.exe", b"binary", content_type="text/plain")
        response = self.client.post(self.url, self.cert_data(document=bad))

        self.assertEqual(response.status_code, 400)
        self.assertIn("document", response.context["cert_form"].errors)
        self.assertEqual(self.provider.certifications.count(), 0)

    def test_missing_document_rejected(self):
        data = self.cert_data()
        del data["document"]
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("document", response.context["cert_form"].errors)

    def test_missing_expires_rejected(self):
        response = self.client.post(self.url, self.cert_data(expires=""))

        self.assertEqual(response.status_code, 400)
        self.assertIn("expires", response.context["cert_form"].errors)

    def test_file_too_large_rejected(self):
        with mock.patch("members.forms.CERT_MAX_UPLOAD_SIZE", 5):
            response = self.client.post(self.url, self.cert_data())

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "File is too large. The limit is 10 MB.", status_code=400
        )
        self.assertEqual(self.provider.certifications.count(), 0)

    def test_duplicate_cert_rejected(self):
        ProviderCert.objects.create(
            provider=self.provider, cert=self.cpr, issuer="American Red Cross"
        )
        response = self.client.post(self.url, self.cert_data())

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "You have already added this certificate.", status_code=400
        )
        self.assertEqual(self.provider.certifications.count(), 1)

    def test_same_cert_allowed_for_different_providers(self):
        other_user = User.objects.create_user(username="ann", password="password")
        other = Provider.objects.create(user=other_user)
        ProviderCert.objects.create(provider=other, cert=self.cpr, issuer="County")

        response = self.client.post(self.url, self.cert_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.provider.certifications.count(), 1)

    def test_errors_keep_add_certificate_panel_open(self):
        response = self.client.post(self.url, self.cert_data(issuer=""))

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, '<details class="add-certificate" open>', status_code=400
        )

    def test_seeker_cannot_add_certificate(self):
        seeker_user = User.objects.create_user(username="sue", password="password")
        Seeker.objects.create(user=seeker_user)
        self.client.login(username="sue", password="password")

        response = self.client.post(self.url, self.cert_data())
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(ProviderCert.objects.count(), 0)


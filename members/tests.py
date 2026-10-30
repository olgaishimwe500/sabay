# Create your tests here.
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import JobPost

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

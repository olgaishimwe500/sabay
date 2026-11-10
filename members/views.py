from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from booking.models import JobPost, JobReq

from .cities import CITIES
from .forms import ProviderCertForm, ProviderPictureForm, ProviderProfileForm

"""
Decided to use a custom login view
- makes sure the request method is post before authenticating
- checks to make sure user exists before calling auth
"""


def login(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is None:
            error = "Invalid username or password"
        elif user.is_staff or user.is_superuser:
            return HttpResponse(
                "Forbidden: use admin login",
                status=403,
                content_type="text/plain",
            )
        else:
            auth_login(request, user)
            if hasattr(user, "provider_profile"):
                return redirect("dashboard")
            return redirect("members:seeker_dashboard")

    return render(request, "auth_logic/login.html", {"error": error})


"""
Using a very simple logout view atm. 
- makes sure the request method is post
"""


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("home")


"""
autofill function uses GET method to simple backend list. 
Will be integrate into front end later
"""


def city_autofill(request):
    city = request.GET.get("city", "").strip().lower()

    if not city:
        return JsonResponse({"results": []})
    results = [c for c in CITIES if city in c.lower()][:10]
    return JsonResponse({"results": results})


"""
Will allow providers to toggle if they are available/accepting jobs.
Hopefully this can replace the availablity deal :)
"""


@login_required
@require_POST
def toggle_availability(request):
    provider = request.user.provider_profile
    provider.is_available = "is_available" in request.POST
    provider.save()
    return redirect("dashboard")


"""
This function will allow providers to see their booking request.
"""


@login_required
def dashboard(request):
    if hasattr(request.user, "provider_profile"):
        provider = getattr(request.user, "provider_profile", None)
        now = timezone.now()
        # Hide jobs whose start time passed before anyone was accepted
        JobPost.objects.expire_past_due(now)
        booking_requests = (
            JobPost.objects.select_related("seeker__user")
            .filter(status="open", provider=provider)
            .order_by("-created_at")[:5]
        )
        upcoming_jobs = (
            JobPost.objects.select_related("seeker__user")
            # Using Q from db.models allows for grouping filters
            .filter(
                Q(status="accepted", provider=provider, schedule_start__gte=now)
                | Q(applications__provider=provider, applications__status="approved")
            )
            .order_by("schedule_start")
        )
        my_request_status = JobReq.objects.filter(
            job=OuterRef("pk"), provider=provider
        ).values("status")[:1]

        dismissed_jobs = JobReq.objects.filter(
            provider=provider, dismissed=True
        ).values("job_id")
        open_jobs = (
            JobPost.objects.select_related("seeker__user")
            .filter(status="open", provider__isnull=True)
            .exclude(applications__provider=provider, applications__status="approved")
            .exclude(pk__in=dismissed_jobs)
            .annotate(my_status=Subquery(my_request_status))
            .order_by("-created_at")
        )
        return render(
            request,
            "providers/dashboard.html",
            {
                "provider": provider,
                "booking_requests": booking_requests,
                "upcoming_jobs": upcoming_jobs[:3],
                "open_jobs": open_jobs[:3],
            },
        )
    elif hasattr(request.user, "seeker_profile"):
        return redirect("home")


"""
Handles if provider accepts a job or declines it
"""


@login_required
@require_POST
def job_response(request, job_id):
    job = get_object_or_404(JobPost, pk=job_id)
    action = request.POST.get("action")
    print("POST data:", request.POST, "| action:", action)
    if action == "accept":
        job.status = "accepted"
    elif action == "decline":
        job.status = "declined"

    job.save()
    job.refresh_from_db()
    print("Saved status:", repr(job.status))
    return redirect("dashboard")


"""
Handles the logic when a provider requests a 
job.
"""


@login_required
@require_POST
def job_request(request, job_id):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")
    job = get_object_or_404(
        JobPost,
        pk=job_id,
        status="open",
        provider__isnull=True,
        schedule_start__gt=timezone.now(),
    )
    JobReq.objects.get_or_create(job=job, provider=provider)
    return redirect("dashboard")


"""
This function will dismiss the job if the provider is not 
selected by the seeker in a job request
"""


@login_required
@require_POST
def dismiss_request(request, job_id):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")

    job_req = get_object_or_404(
        JobReq, job_id=job_id, provider=provider, status="declined"
    )
    job_req.dismissed = True
    job_req.save(update_fields=["dismissed"])
    return redirect("dashboard")


"""
This will render the providers profile and will
allow them to edit it
"""


@login_required
def provider_profile_edit(request):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")
    return render_provider_profile(request, provider)


def render_provider_profile(
    request,
    provider,
    picture_form=None,
    profile_form=None,
    cert_form=None,
    status=200,
):
    """
    Renders the provider's edit profile page. Views that fail validation
    pass in their bound form so its errors show up on the page.
    """
    return render(
        request,
        "providers/profile.html",
        {
            "provider": provider,
            "picture_form": picture_form or ProviderPictureForm(),
            "profile_form": profile_form or ProviderProfileForm(instance=provider),
            "cert_form": cert_form or ProviderCertForm(provider=provider),
            "certifications": provider.certifications.select_related("cert").order_by(
                "cert__name"
            ),
        },
        status=status,
    )


"""
Uploads a new profile picture for the provider.
- the form's ImageField makes sure the upload is a real image
- the old picture file is removed so it doesn't pile up in media/
"""


@login_required
@require_POST
def add_profile_picture(request):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")

    old_picture = provider.profilePicture.name if provider.profilePicture else None
    form = ProviderPictureForm(request.POST, request.FILES, instance=provider)
    if not form.is_valid():
        # Reload the current picture since the failed form changed the instance
        provider.refresh_from_db()
        return render_provider_profile(request, provider, picture_form=form, status=400)

    form.save()
    if old_picture and old_picture != provider.profilePicture.name:
        provider.profilePicture.storage.delete(old_picture)
    return redirect("members:provider_profile_edit")


"""
Removes the provider's profile picture and deletes the file.
"""


@login_required
@require_POST
def remove_profile_picture(request):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")

    if provider.profilePicture:
        # delete() removes the file from storage and saves the model
        provider.profilePicture.delete(save=False)
        provider.profilePicture = None
        provider.save(update_fields=["profilePicture"])
    return redirect("members:provider_profile_edit")


"""
Saves the provider profile page: city, bio,
whether they are accepting new jobs, and their specialties.
"""


@login_required
@require_POST
def update_provider_profile(request):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")

    form = ProviderProfileForm(request.POST, instance=provider)
    if not form.is_valid():
        provider.refresh_from_db()
        return render_provider_profile(request, provider, profile_form=form, status=400)

    form.save()
    return redirect("members:provider_profile_edit")


"""
Uploads a certificate (photo or PDF) for the provider.
- new certificates always start unverified until an admin reviews them
"""


@login_required
@require_POST
def add_certificate(request):
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("home")

    form = ProviderCertForm(request.POST, request.FILES, provider=provider)
    if not form.is_valid():
        return render_provider_profile(request, provider, cert_form=form, status=400)

    provider_cert = form.save(commit=False)
    provider_cert.provider = provider
    provider_cert.is_verified = False
    provider_cert.save()
    return redirect("members:provider_profile_edit")

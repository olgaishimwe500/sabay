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
            return redirect("home")

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
    job = get_object_or_404(JobPost, pk=job_id, status="open", provider__isnull=True)
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

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from booking.models import JobPost

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

        if user is not None:
            auth_login(request, user)
            if hasattr(request.user, "provider_profile"):
                return redirect("dashboard")

            elif hasattr(request.user, "seeker_profile"):
                return redirect("home")
        else:
            error = "Invalid username or password"

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
            .filter(status="accepted", provider=provider, schedule_start__gte=now)
            .order_by("schedule_start")
        )
        open_jobs = (
            JobPost.objects.select_related("seeker__user")
            .filter(status="open")
            .order_by("-created_at")
        )
        return render(
            request,
            "providers/dashboard.html",
            {
                "provider": provider,
                "booking_requests": booking_requests,
                "upcoming_jobs": upcoming_jobs[:3],
                "open_jobs": open_jobs[:3]
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

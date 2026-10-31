from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import SeekerProfileForm
from .models import Seeker
from booking.models import JobReq


@login_required
def seeker_profile(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    jobs = seeker.job_posts.order_by("-created_at")
    return render(
        request, "members/seeker_profile.html", {"seeker": seeker, "jobs": jobs}
    )


@login_required
def seeker_profile_edit(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    form = SeekerProfileForm(
        request.POST or None, request.FILES or None, instance=seeker
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("members:seeker_profile")
    return render(request, "members/seeker_profile_edit.html", {"form": form})

@login_required
def seeker_dashboard(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    jobs = seeker.job_posts.all()

    pending_reqs=( JobReq.objects.filter(job__seeker=seeker, status="pending", job__status="open").select_related("job", "provider__user").order_by("job__schedule_start"))
    open_jobs = (jobs.filter(status="open").exclude(applications__status="pending").order_by("schedule_start"))
    upcoming_jobs=jobs.filter(status="accepted").order_by("schedule_start")[:3]

    context={"seeker": seeker,
            "pending_reqs": pending_reqs,
            "open_jobs": open_jobs,
            "upcoming_jobs": upcoming_jobs,}

    return render(request, "members/seeker_dashboard.html", context)
    

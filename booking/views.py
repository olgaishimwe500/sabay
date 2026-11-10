from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from members.models import Seeker

from .forms import JobPostForm
from .models import JobPost, JobReq


# Create your views here.
@login_required
def post_job(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    form = JobPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.seeker = seeker
        job.save()
        return redirect("members:seeker_dashboard")
    return render(request, "booking/post_job.html", {"form": form})


@login_required
def job_list(request):
    if not hasattr(request.user, "provider_profile"):
        return redirect("members:seeker_dashboard")
    JobPost.objects.expire_past_due()
    jobs = JobPost.objects.select_related("seeker__user").order_by("-created_at")
    return render(request, "booking/job_list.html", {"jobs": jobs})


@login_required
def job_detail(request, pk):
    JobPost.objects.expire_past_due()
    job = get_object_or_404(JobPost.objects.select_related("seeker__user"), pk=pk)
    return render(request, "booking/job_detail.html", {"job": job})


@login_required
@require_POST
def confirm(request, pk):
    req = get_object_or_404(
        JobReq,
        pk=pk,
        job__seeker__user=request.user,
        status="pending",
        job__status="open",
    )
    req.approve()
    return redirect("members:seeker_dashboard")


@login_required
@require_POST
def decline(request, pk):
    req = get_object_or_404(
        JobReq,
        pk=pk,
        job__seeker__user=request.user,
        status="pending",
        job__status="open",
    )
    req.status = "declined"
    req.save()
    return redirect("members:seeker_dashboard")

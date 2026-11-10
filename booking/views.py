from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from members.models import Seeker

from .forms import JobPostForm
from .models import JobPost, JobReq


# Create your views here.
@login_required
def post_job(request):
    # Only care seekers post jobs; providers browse them on the job board
    if hasattr(request.user, "provider_profile"):
        return redirect("booking:job_list")
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
    provider = getattr(request.user, "provider_profile", None)
    if provider is None:
        return redirect("members:seeker_dashboard")
    now = timezone.now()
    JobPost.objects.expire_past_due(now)
    # This provider's request status for each job (None if not requested)
    my_request_status = JobReq.objects.filter(
        job=OuterRef("pk"), provider=provider
    ).values("status")[:1]
    # Expired jobs and jobs this provider was not selected for are hidden
    jobs = list(
        JobPost.objects.select_related("seeker__user")
        .exclude(status="expired")
        .exclude(applications__provider=provider, applications__status="declined")
        .annotate(my_status=Subquery(my_request_status))
        .order_by("-created_at")
    )
    selected_id = request.GET.get("job")
    selected = next((job for job in jobs if str(job.pk) == selected_id), None)
    return render(
        request,
        "booking/job_list.html",
        {
            "jobs": jobs,
            "selected": selected or (jobs[0] if jobs else None),
            "has_selection": selected is not None,
            "now": now,
        },
    )


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

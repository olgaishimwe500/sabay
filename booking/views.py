from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from members.models import Seeker
from .forms import JobPostForm
from .models import JobPost

# Create your views here.
@login_required
def post_job(request):
    seeker, _= Seeker.objects.get_or_create(user=request.user)
    form = JobPostForm(request.POST or None)
    if request.method =="POST" and form.is_valid():
        job = form.save(commit=False)
        job.seeker = seeker
        job.save()
        return redirect("booking:job_list")
    return render(request, "booking/post_job.html", {"form": form})

@login_required
def job_list(request):
    jobs = JobPost.objects.select_related("seeker__user").order_by("-created_at")
    return render(request, "booking/job_list.html", {"jobs": jobs})

@login_required
def job_detail(request, pk):
    job = get_object_or_404(JobPost.objects.select_related("seeker__user"), pk=pk)
    return render(request, "booking/job_detail.html", {"job": job})
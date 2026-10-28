from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import SeekerProfileForm
from .models import Seeker

@login_required
def seeker_profile(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    jobs = seeker.job_posts.order_by("-created_at")
    return render(request, "members/seeker_profile.html", {"seeker":seeker, "jobs": jobs })

@login_required
def seeker_profile_edit(request):
    seeker, _ = Seeker.objects.get_or_create(user=request.user)
    form = SeekerProfileForm(request.POST or None, request.FILES or None, instance=seeker)
    if request.method =="POST" and form.is_valid():
        form.save()
        return redirect("members:seeker_profile")
    return render(request, "members/seeker_profile_edit.html", {"form": form})
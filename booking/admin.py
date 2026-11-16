from django.contrib import admin

from .models import JobPost, JobReq

# Register your models here.

@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = ("seeker", "task_type", "schedule_start", "schedule_end", "status")

@admin.register(JobReq)
class JobReqAdmin(admin.ModelAdmin):
    list_display = ( "provider", "status")

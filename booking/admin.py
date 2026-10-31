from django.contrib import admin

from .models import JobPost, JobReq

# Register your models here.
admin.site.register(JobPost)
admin.site.register(JobReq)

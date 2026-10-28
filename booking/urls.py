from django.urls import path
from . import views

app_name = "booking"
urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("post/", views.post_job, name="post_job"),
    path("<int:pk>/", views.job_detail, name="job_detail"),
]
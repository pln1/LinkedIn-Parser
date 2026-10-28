from django.urls import path
from jobs import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("queries/", views.QueryListView.as_view(), name="query_list"),
    path("queries/create/", views.create_query_view, name="query_create"),
    path("queries/<int:pk>/run/", views.trigger_query_scrape, name="query_run"),
    path("jobs/<int:pk>/", views.job_detail_api, name="job_detail_api"),
    path("jobs/export/csv/", views.export_jobs_csv, name="job_export_csv"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]

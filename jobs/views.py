import threading
import csv
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView
from jobs.models import Job, SearchQuery


class JobListView(LoginRequiredMixin, ListView):
    model = Job
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 12

    def get_queryset(self):
        qs = Job.objects.select_related("search_query").order_by("-created_at")
        query = self.request.GET.get("q")
        status = self.request.GET.get("status")
        employment = self.request.GET.get("employment")

        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(company_name__icontains=query)
                | Q(location__icontains=query)
                | Q(description__icontains=query)
            )
        if status:
            qs = qs.filter(status=status)
        if employment:
            qs = qs.filter(employment_type__icontains=employment)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_count"] = Job.objects.count()
        ctx["detailed_count"] = Job.objects.filter(
            status=Job.StatusChoices.DETAILED
        ).count()
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["selected_query"] = self.request.GET.get("q", "")
        ctx["selected_employment"] = self.request.GET.get("employment", "")
        return ctx


class QueryListView(LoginRequiredMixin, ListView):
    model = SearchQuery
    template_name = "jobs/query_list.html"
    context_object_name = "queries"
    ordering = ["-created_at"]


@login_required
def create_query_view(request):
    if request.method == "POST":
        keyword = request.POST.get("keyword", "").strip()
        country = request.POST.get("country", "").strip()
        max_pages = int(request.POST.get("max_pages", 40))

        if keyword and country:
            query, created = SearchQuery.objects.get_or_create(
                keyword=keyword,
                country=country,
                defaults={"max_pages": max_pages, "is_active": True},
            )
            if not created:
                query.max_pages = max_pages
                query.is_active = True
                query.save()

            messages.success(
                request,
                f"Search query '{keyword}' ({country}) successfully registered.",
            )
        return redirect("jobs:query_list")
    return redirect("jobs:query_list")


@login_required
def trigger_query_scrape(request, pk):
    query = get_object_or_404(SearchQuery, pk=pk)

    def _worker():
        try:
            call_command("scrape_search", query_id=query.id)
            call_command("scrape_details", limit=1000)
        except Exception as exc:
            print(f"[Worker Error] Failed execution: {exc}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    messages.info(
        request,
        f"Scraping pipeline for '{query.keyword}' started in background. New jobs will appear shortly.",
    )
    return redirect("jobs:query_list")


@login_required
def job_detail_api(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse(
        {
            "id": job.id,
            "title": job.title,
            "company_name": job.company_name,
            "location": job.location,
            "status": job.status,
            "description": job.description
            or "Full description has not been fetched yet.",
            "employment_type": job.employment_type or "—",
            "seniority_level": job.seniority_level or "—",
            "industries": job.industries or "—",
            "job_url": job.job_url,
            "apply_url": job.apply_url or job.job_url,
        }
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect("jobs:job_list")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("jobs:job_list")
    else:
        form = UserCreationForm()
    return render(request, "jobs/auth/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("jobs:job_list")
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("jobs:job_list")
    else:
        form = AuthenticationForm()
    return render(request, "jobs/auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("jobs:login")


@login_required
def export_jobs_csv(request):
    qs = Job.objects.select_related("search_query").order_by("-created_at")
    query = request.GET.get("q")
    status = request.GET.get("status")
    employment = request.GET.get("employment")

    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(company_name__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
        )
    if status:
        qs = qs.filter(status=status)
    if employment:
        qs = qs.filter(employment_type__icontains=employment)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="linkedin_jobs_export.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    headers = [
        "LinkedIn Job ID",
        "Status",
        "Title",
        "Company Name",
        "Location",
        "Employment Type",
        "Seniority Level",
        "Job Function",
        "Industries",
        "Listed Date",
        "Applicants Count",
        "Job URL",
        "Apply URL",
        "Company LinkedIn URL",
        "Company Logo URL",
        "Search Query",
        "Description",
    ]
    writer.writerow(headers)

    for job in qs.iterator(chunk_size=500):
        writer.writerow(
            [
                job.linkedin_job_id,
                job.status,
                job.title,
                job.company_name,
                job.location,
                job.employment_type,
                job.seniority_level,
                job.job_function,
                job.industries,
                job.listed_at or job.posted_date_text,
                job.applicants_count,
                job.job_url,
                job.apply_url,
                job.company_linkedin_url,
                job.company_logo_url,
                str(job.search_query) if job.search_query else "",
                job.description,
            ]
        )

    return response

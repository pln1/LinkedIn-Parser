import csv
from io import BytesIO
import threading
import openpyxl
from django.contrib import admin, messages
from django.core.management import call_command
from django.http import HttpResponse
from django.utils.html import format_html
from jobs.models import Job, SearchQuery


def _run_search_thread(query_id: int):
    """Background worker for Stage 1 (Search Scraper)"""
    try:
        call_command("scrape_search", query_id=query_id)
    except Exception as exc:
        print(f"[Scraper Error] Failure during search query (ID={query_id}): {exc}")


def _run_details_thread(limit: int):
    """Background worker for Stage 2 (Details Scraper)"""
    try:
        call_command("scrape_details", limit=limit)
    except Exception as exc:
        print(f"[Scraper Error] Failure during detail processing: {exc}")


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = (
        "keyword",
        "country",
        "is_active",
        "max_pages",
        "total_jobs_count",
        "detailed_jobs_count",
        "last_scraped_at",
    )
    list_filter = ("is_active", "country")
    search_fields = ("keyword", "country")
    list_editable = ("is_active", "max_pages")
    actions = ["run_search_for_selected", "run_full_cycle_for_selected"]

    def total_jobs_count(self, obj):
        return obj.jobs.count()

    total_jobs_count.short_description = "Total Jobs"

    def detailed_jobs_count(self, obj):
        return obj.jobs.filter(status=Job.StatusChoices.DETAILED).count()

    detailed_jobs_count.short_description = "Detailed Jobs"

    @admin.action(description="⚡ Run Search Scraper for selected queries (Stage 1)")
    def run_search_for_selected(self, request, queryset):
        count = 0
        for query in queryset:
            thread = threading.Thread(
                target=_run_search_thread, args=(query.id,), daemon=True
            )
            thread.start()
            count += 1
        self.message_user(
            request,
            f"Background search scraper initiated for {count} query record(s). Refresh the page shortly.",
            messages.SUCCESS,
        )

    @admin.action(description="🚀 Run Full Scrape Pipeline (Search + Details)")
    def run_full_cycle_for_selected(self, request, queryset):
        def _full_cycle():
            for query in queryset:
                try:
                    call_command("scrape_search", query_id=query.id)
                except Exception as exc:
                    print(f"Search scraper error: {exc}")
            try:
                call_command("scrape_details", limit=1000)
            except Exception as exc:
                print(f"Details scraper error: {exc}")

        thread = threading.Thread(target=_full_cycle, daemon=True)
        thread.start()
        self.message_user(
            request,
            "Complete scraping pipeline launched in background. New jobs will populate the Jobs table.",
            messages.SUCCESS,
        )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "linkedin_job_id",
        "title",
        "company_name",
        "location",
        "colored_status",
        "employment_type",
        "seniority_level",
        "listed_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "employment_type",
        "seniority_level",
        "search_query",
        "listed_at",
    )
    search_fields = (
        "linkedin_job_id",
        "title",
        "company_name",
        "location",
        "description",
    )
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    actions = [
        "run_details_scraper_now",
        "mark_as_pending",
        "export_as_csv",
        "export_as_excel",
    ]

    def colored_status(self, obj):
        colors = {
            Job.StatusChoices.PENDING: "#f39c12",
            Job.StatusChoices.DETAILED: "#27ae60",
            Job.StatusChoices.FAILED: "#c0392b",
        }
        color = colors.get(obj.status, "#000000")
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.status,
        )

    colored_status.short_description = "Status"

    @admin.action(description="⚡ Fetch descriptions for Pending jobs (Stage 2)")
    def run_details_scraper_now(self, request, queryset):
        thread = threading.Thread(target=_run_details_thread, args=(200,), daemon=True)
        thread.start()
        self.message_user(
            request,
            "Background detail scraper launched for up to 200 pending vacancies.",
            messages.SUCCESS,
        )

    @admin.action(description="Reset selected jobs status to Pending")
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(
            status=Job.StatusChoices.PENDING, retry_count=0, error_message=""
        )
        self.message_user(
            request, f"{updated} vacancy records reset to Pending.", messages.SUCCESS
        )

    @admin.action(description="Export selected jobs to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="linkedin_jobs_export.csv"'
        )
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

        for job in queryset.select_related("search_query").iterator():
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

    @admin.action(description="Export selected jobs to Excel (.xlsx)")
    def export_as_excel(self, request, queryset):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "LinkedIn Jobs"

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
        ws.append(headers)

        for job in queryset.select_related("search_query").iterator():
            ws.append(
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
                    str(job.listed_at or job.posted_date_text),
                    job.applicants_count,
                    job.job_url,
                    job.apply_url,
                    job.company_linkedin_url,
                    job.company_logo_url,
                    str(job.search_query) if job.search_query else "",
                    job.description,
                ]
            )

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="linkedin_jobs_export.xlsx"'
        )
        return response

import csv
import openpyxl
from django.core.management.base import BaseCommand
from jobs.models import Job


class Command(BaseCommand):
    help = "Export scraped vacancies into CSV or Excel (.xlsx) spreadsheet formats"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="detailed_jobs.xlsx",
            help="Target output file path (.csv or .xlsx extensions supported)",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Export jobs across all statuses (default exports Detailed only)",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        queryset = Job.objects.select_related("search_query").all()

        if not options["all_statuses"]:
            queryset = queryset.filter(status=Job.StatusChoices.DETAILED)

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

        if output_path.endswith(".xlsx"):
            wb = openpyxl.Workbook(write_only=True)
            ws = wb.create_sheet("Jobs")
            ws.append(headers)
            count = 0
            for job in queryset.iterator(chunk_size=500):
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
                        str(job.search_query or ""),
                        job.description,
                    ]
                )
                count += 1
            wb.save(output_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported {count} records to Excel: {output_path}"
                )
            )
        else:
            with open(output_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                count = 0
                for job in queryset.iterator(chunk_size=500):
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
                            str(job.search_query or ""),
                            job.description,
                        ]
                    )
                    count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported {count} records to CSV: {output_path}"
                )
            )

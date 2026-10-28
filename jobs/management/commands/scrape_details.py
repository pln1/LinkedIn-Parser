import logging
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction
from jobs.models import Job
from jobs.services.http_client import LinkedInHTTPClient

logger = logging.getLogger("scraper")
DETAIL_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class Command(BaseCommand):
    help = "Stage 2: Fetch detailed descriptions, criteria, and company data for Pending jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum records to process in a single run (default: 1000)",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Retry postings previously marked as Failed (retry count < 3)",
        )

    def handle(self, *args, **options):
        client = LinkedInHTTPClient(min_delay=1.0, max_delay=2.5)
        limit = options["limit"]

        statuses = [Job.StatusChoices.PENDING]
        if options["retry_failed"]:
            statuses.append(Job.StatusChoices.FAILED)

        queryset = Job.objects.filter(status__in=statuses, retry_count__lt=3).order_by(
            "created_at"
        )[:limit]

        total_to_process = queryset.count()
        if total_to_process == 0:
            logger.info("No Pending jobs requiring detail extraction.")
            return

        logger.info(
            f"Commencing detailed extraction for {total_to_process} job postings..."
        )
        success_count = 0
        failed_count = 0

        for idx, job in enumerate(queryset.iterator(chunk_size=100), start=1):
            url = DETAIL_API_URL.format(job_id=job.linkedin_job_id)
            try:
                response = client.get(url)

                if response.status_code == 404:
                    job.status = Job.StatusChoices.FAILED
                    job.error_message = (
                        "HTTP 404: Vacancy deleted, closed, or no longer accessible."
                    )
                    job.retry_count = 3
                    job.save(
                        update_fields=[
                            "status",
                            "error_message",
                            "retry_count",
                            "updated_at",
                        ]
                    )
                    failed_count += 1
                    logger.warning(
                        f"[{idx}/{total_to_process}] Job {job.linkedin_job_id}: 404 Not Found"
                    )
                    continue

                if response.status_code != 200 or not response.text.strip():
                    raise RuntimeError(
                        f"Unexpected HTTP status code: {response.status_code}"
                    )

                self._parse_and_populate_job(job, response.text)
                job.status = Job.StatusChoices.DETAILED
                job.error_message = ""

                with transaction.atomic():
                    job.save()

                success_count += 1
                logger.info(
                    f"[{idx}/{total_to_process}] Updated [{job.linkedin_job_id}] {job.title}"
                )

            except KeyboardInterrupt:
                logger.warning("Terminated by user. Stored modifications preserved.")
                break
            except Exception as exc:
                job.retry_count += 1
                job.error_message = str(exc)
                if job.retry_count >= 3:
                    job.status = Job.StatusChoices.FAILED
                job.save(
                    update_fields=[
                        "status",
                        "retry_count",
                        "error_message",
                        "updated_at",
                    ]
                )
                failed_count += 1
                logger.error(
                    f"[{idx}/{total_to_process}] Exception for Job {job.linkedin_job_id}: {exc}"
                )

        logger.info(
            f"Detail processing completed. Successfully Detailed: {success_count}, Errors: {failed_count}"
        )

    def _parse_and_populate_job(self, job: Job, html: str):
        soup = BeautifulSoup(html, "lxml")

        # Full vacancy description
        desc_div = soup.find("div", class_="show-more-less-html__markup")
        if desc_div:
            job.description = desc_div.get_text(separator="\n", strip=True)

        # Company profile and logo
        topcard_company = soup.find("a", class_="topcard__org-name-link") or soup.find(
            "span", class_="topcard__flavor"
        )
        if topcard_company:
            job.company_name = topcard_company.get_text(strip=True)
            if topcard_company.name == "a" and topcard_company.has_attr("href"):
                job.company_linkedin_url = topcard_company["href"].split("?")[0]

        logo_img = soup.find("img", class_="artdeco-entity-image")
        if logo_img:
            job.company_logo_url = logo_img.get("data-delayed-url") or logo_img.get(
                "src", ""
            )

        # Direct submission URL
        apply_btn = (
            soup.find("a", class_="topcard__link")
            or soup.find(
                "a",
                attrs={"data-tracking-control-name": "public_jobs_apply-link-offsite"},
            )
            or soup.find("button", class_="apply-button")
        )
        if apply_btn and apply_btn.name == "a" and apply_btn.has_attr("href"):
            job.apply_url = apply_btn["href"]
        else:
            job.apply_url = job.job_url

        # Criteria fields
        criteria_items = soup.find_all("li", class_="description__job-criteria-item")
        for item in criteria_items:
            header_el = item.find("h3", class_="description__job-criteria-subheader")
            value_el = item.find("span", class_="description__job-criteria-text")
            if not header_el or not value_el:
                continue

            header_text = header_el.get_text(strip=True).lower()
            val = value_el.get_text(strip=True)

            if val.lower() in ["not applicable", "n/a", "none"]:
                val = ""

            if "seniority" in header_text:
                job.seniority_level = val
            elif "employment" in header_text:
                job.employment_type = val
            elif "function" in header_text:
                job.job_function = val
            elif "industries" in header_text:
                job.industries = val

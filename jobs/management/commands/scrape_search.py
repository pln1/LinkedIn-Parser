import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job, SearchQuery
from jobs.services.http_client import LinkedInHTTPClient

logger = logging.getLogger("scraper")
SEARCH_API_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)


class Command(BaseCommand):
    help = "Stage 1: Collect base job listing cards matching active SearchQuery records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--query-id",
            type=int,
            help="Run scraper exclusively for a specific SearchQuery ID",
        )

    def handle(self, *args, **options):
        client = LinkedInHTTPClient(min_delay=1.0, max_delay=2.5)
        queries = SearchQuery.objects.filter(is_active=True)

        if options["query_id"]:
            queries = queries.filter(id=options["query_id"])

        if not queries.exists():
            logger.info("No active search queries available for processing.")
            return

        for query in queries:
            logger.info(
                f"Starting search collection for: '{query.keyword}' in '{query.country}'"
            )
            self._scrape_all_available(client, query)
            query.last_scraped_at = timezone.now()
            query.save(update_fields=["last_scraped_at", "updated_at"])

    def _scrape_all_available(self, client: LinkedInHTTPClient, query: SearchQuery):
        total_created = 0
        consecutive_empty = 0
        start_offset = 0

        raw_keyword = query.keyword.strip()
        search_term = (
            f'"{raw_keyword}"'
            if len(raw_keyword) <= 4 and not raw_keyword.startswith('"')
            else raw_keyword
        )

        while True:
            params = {
                "keywords": search_term,
                "location": query.country,
                "start": start_offset,
            }

            try:
                response = client.get(SEARCH_API_URL, params=params)
                if response.status_code != 200 or not response.text.strip():
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        logger.info(
                            f"Reached end of LinkedIn listings at start offset={start_offset}."
                        )
                        break
                    start_offset += 25
                    continue

                jobs_batch = self._parse_search_html(response.text, query)
                if not jobs_batch:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        logger.info(
                            f"No additional postings returned at start offset={start_offset}."
                        )
                        break
                    start_offset += 25
                    continue

                consecutive_empty = 0
                created = Job.objects.bulk_create(jobs_batch, ignore_conflicts=True)
                batch_count = len(created)
                total_created += batch_count

                logger.info(
                    f"[{query}] Offset start={start_offset}: "
                    f"Parsed={len(jobs_batch)}, Inserted New={batch_count}"
                )
                start_offset += 25

            except KeyboardInterrupt:
                logger.warning(
                    "Interrupted by user (SIGINT). Stored progress preserved."
                )
                break
            except Exception as exc:
                logger.error(
                    f"Error processing start offset {start_offset} for {query}: {exc}"
                )
                start_offset += 25

        logger.info(
            f"Finished query '{query.keyword}': inserted {total_created} new jobs into database."
        )

    def _parse_search_html(self, html: str, query: SearchQuery) -> list[Job]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("li")
        jobs = []
        seen = set()

        clean_kw = query.keyword.strip().strip('"').lower()

        for card in cards:
            base_card = card.find("div", class_="base-card")
            if not base_card:
                continue

            urn = base_card.get("data-entity-urn", "")
            match = re.search(r"jobPosting:(\d+)", urn)
            if not match:
                continue

            job_id = match.group(1)
            if job_id in seen:
                continue
            seen.add(job_id)

            title_el = card.find("h3", class_="base-search-card__title")
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"

            company_el = card.find("h4", class_="base-search-card__subtitle")
            company = company_el.get_text(strip=True) if company_el else ""

            # Prevent false positives for short tokens (e.g., 'Go' matching company 'Tango')
            if clean_kw == "go":
                has_go_in_title = bool(
                    re.search(r"\b(go|golang)\b", title, re.IGNORECASE)
                )
                if not has_go_in_title and "tango" in company.lower():
                    continue

            link_el = card.find("a", class_="base-card__full-link")
            url = (
                link_el["href"].split("?")[0]
                if link_el and link_el.has_attr("href")
                else f"https://www.linkedin.com/jobs/view/{job_id}/"
            )

            company_link_el = company_el.find("a") if company_el else None
            company_url = (
                company_link_el["href"].split("?")[0]
                if company_link_el and company_link_el.has_attr("href")
                else ""
            )

            location_el = card.find("span", class_="job-search-card__location")
            location = location_el.get_text(strip=True) if location_el else ""

            time_el = card.find("time")
            posted_date_text = time_el.get_text(strip=True) if time_el else ""
            listed_at = None
            if time_el and time_el.has_attr("datetime"):
                try:
                    listed_at = datetime.strptime(
                        time_el["datetime"], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass

            jobs.append(
                Job(
                    linkedin_job_id=job_id,
                    search_query=query,
                    status=Job.StatusChoices.PENDING,
                    title=title,
                    job_url=url,
                    location=location,
                    posted_date_text=posted_date_text,
                    listed_at=listed_at,
                    company_name=company,
                    company_linkedin_url=company_url,
                )
            )

        return jobs

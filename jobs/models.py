from django.db import models


class SearchQuery(models.Model):
    keyword = models.CharField(
        max_length=255,
        help_text="Search keyword (e.g., 'Python Developer', 'Golang Engineer')",
    )
    country = models.CharField(
        max_length=150,
        help_text="Target country or location (e.g., 'USA', 'Germany', 'Poland')",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Active status for automated search scrapers",
    )
    max_pages = models.PositiveIntegerField(
        default=40,
        help_text="Pagination page limit (1 page = 25 postings; 40 pages = 1,000 postings)",
    )
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Search Query"
        verbose_name_plural = "Search Queries"
        unique_together = ("keyword", "country")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.keyword} ({self.country})"


class Job(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "Pending", "Pending"
        DETAILED = "Detailed", "Detailed"
        FAILED = "Failed", "Failed"

    linkedin_job_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique LinkedIn vacancy identifier",
    )
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        db_index=True,
    )

    # Basic job metadata (Stage 1)
    title = models.CharField(max_length=500)
    job_url = models.URLField(max_length=1000)
    location = models.CharField(max_length=255, blank=True, default="")
    posted_date_text = models.CharField(max_length=100, blank=True, default="")
    listed_at = models.DateField(null=True, blank=True)

    # Detailed specifications (Stage 2)
    description = models.TextField(blank=True, default="")
    seniority_level = models.CharField(max_length=150, blank=True, default="")
    employment_type = models.CharField(max_length=150, blank=True, default="")
    job_function = models.CharField(max_length=255, blank=True, default="")
    industries = models.CharField(max_length=255, blank=True, default="")
    applicants_count = models.CharField(max_length=100, blank=True, default="")
    apply_url = models.URLField(max_length=1000, blank=True, default="")

    # Company specifications (Stage 1 + Stage 2)
    company_name = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    company_linkedin_url = models.URLField(max_length=1000, blank=True, default="")
    company_logo_url = models.URLField(max_length=1000, blank=True, default="")

    # Diagnostics and retry tracking
    retry_count = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "retry_count"]),
        ]

    def __str__(self):
        return f"[{self.linkedin_job_id}] {self.title} at {self.company_name}"

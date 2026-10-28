 LinkedIn Job Radar & Two-Stage Scraper (Django + PostgreSQL)

A production-ready LinkedIn job aggregation and scraping system built with **Python**, **Django**, **PostgreSQL**.


---

## Key Features

1. **Two-Phase Independent Scraping Architecture (No Selenium)**:
   * **Phase 1 (Search Scraper)**: Reads active `SearchQuery` records, paginates through LinkedIn's internal guest search API, extracts preliminary job cards, and performs batch inserts with a `Pending` status.
   * **Phase 2 (Details Scraper)**: Queries `Pending` jobs, retrieves full job descriptions, seniority levels, employment types, industry classifications, company links/logos, and direct application URLs, transitioning records to `Detailed` (or `Failed` on HTTP 404/permanent errors).
2. **Resilience & Fault Tolerance**:
   * Randomized request jitter delays (`1.0s – 3.0s`) and automatic User-Agent header rotation.
   * Built-in `HTTP 429 Too Many Requests` handling using exponential backoff.
   * Safe pause/resume capability (`Ctrl+C`) with zero data loss or duplicate entries.
3. **Modern Web UI & Authentication**:
   * Responsive dark-themed dashboard built with Tailwind CSS.
   * Full user authentication (`/login/`, `/register/`, `/logout/`).
   * Live search, status filtering, interactive modal window for full job descriptions, and **1-Click Background Scraping** directly from the web interface.
   * **Direct CSV Export in UI**: Download the currently filtered job listings as a CSV file in 1-click with zero terminal commands.
4. **Rich Django Admin & Data Export**:
   * Dedicated management panels for `Search Queries` and `Jobs` with color-coded statuses.
   * 1-Click background scraping actions and bulk exports to **CSV**.

---

## Project Structure

```text
linkedin_scraper/
├── .env                        # Environment variables (DB credentials & Django settings)
├── .gitignore                  # Git ignore rules
├── manage.py                   # Django CLI entrypoint
├── requirements.txt            # Python package dependencies
├── README.md                   # Project documentation
├── scraper.log                 # Automated runtime log file (generated on execution)
├── core/                       # Main project configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── jobs/                       # Primary scraping & job management application
│   ├── __init__.py
│   ├── admin.py                # Custom Admin panels, 1-click triggers & CSV/XLSX export actions
│   ├── apps.py
│   ├── models.py               # SearchQuery and Job PostgreSQL models
│   ├── urls.py                 # Web UI routing
│   ├── views.py                # Frontend views, API endpoints & background task triggers
│   ├── migrations/             # Database schema migrations
│   ├── services/
│   │   ├── __init__.py
│   │   └── http_client.py      # Resilient HTTP client with retry & backoff policies
│   └── management/
│       └── commands/
│           ├── scrape_search.py   # Phase 1 CLI command: Search Scraper
│           ├── scrape_details.py  # Phase 2 CLI command: Details Scraper
│           ├── export_jobs.py     # CLI command: Bulk CSV / Excel exporter
│           └── clear_jobs.py      # CLI command: Database cleanup utility
└── templates/                  # Frontend HTML templates (Tailwind CSS)
    └── jobs/
        ├── base.html
        ├── job_list.html
        ├── query_list.html
        └── auth/
            ├── login.html
            └── register.html
```

---

## System Prerequisites

Before setting up the project, ensure the following software is installed on your machine:
* **Python**: `3.10`, `3.11`, or `3.12`
* **PostgreSQL**: `14+` (compatible with PostgreSQL 15, 16, 17, and 18)
* **Git**

---

## Step-by-Step Installation Guide

### 1. Clone the Repository
Open your terminal (or PowerShell on Windows) and clone the project:
```bash
git clone <repository-url> linkedin_scraper
cd linkedin_scraper
```

### 2. Create and Activate a Virtual Environment

* **Windows (PowerShell)**:
  ```powershell
  python -m venv venv
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\venv\Scripts\Activate.ps1
  ```
* **Linux / macOS**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## PostgreSQL Database Configuration

You can configure the PostgreSQL database using either the `psql` command-line tool or **pgAdmin 4**.

### Option A: Using the `psql` CLI
1. Log into PostgreSQL as the superuser (`postgres`):
   ```bash
   psql -U postgres
   ```
2. Run the following SQL commands one by one:
   ```sql
   CREATE DATABASE linkedin_jobs_db ENCODING 'UTF8';
   CREATE USER scraper_user WITH PASSWORD 'strong_password';
   ALTER ROLE scraper_user SET client_encoding TO 'utf8';
   ALTER ROLE scraper_user SET default_transaction_isolation TO 'read committed';
   ALTER ROLE scraper_user SET timezone TO 'UTC';
   GRANT ALL PRIVILEGES ON DATABASE linkedin_jobs_db TO scraper_user;
   ALTER DATABASE linkedin_jobs_db OWNER TO scraper_user;
   \c linkedin_jobs_db
   GRANT ALL ON SCHEMA public TO scraper_user;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO scraper_user;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO scraper_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO scraper_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO scraper_user;
   \q
   ```

### Option B: Using pgAdmin 4
1. Open **pgAdmin 4** and connect to your PostgreSQL server.
2. Right-click **Databases** -> **Create** -> **Database...**, enter `linkedin_jobs_db` as the Database name, and click **Save**.
3. Open the **Query Tool** on `linkedin_jobs_db` and execute:
   ```sql
   CREATE USER scraper_user WITH PASSWORD 'strong_password';
   ALTER ROLE scraper_user SET client_encoding TO 'utf8';
   ALTER ROLE scraper_user SET default_transaction_isolation TO 'read committed';
   ALTER ROLE scraper_user SET timezone TO 'UTC';
   GRANT ALL PRIVILEGES ON DATABASE linkedin_jobs_db TO scraper_user;
   ALTER DATABASE linkedin_jobs_db OWNER TO scraper_user;
   GRANT ALL ON SCHEMA public TO scraper_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO scraper_user;
   ```

---

## Environment Variables (`.env`)

Create a `.env` file in the root directory of the project (next to `manage.py`) and populate it with your database credentials:

```env
DJANGO_SECRET_KEY=django-insecure-production-secret-key-change-me
DEBUG=True
POSTGRES_DB=linkedin_jobs_db
POSTGRES_USER=scraper_user
POSTGRES_PASSWORD=strong_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

## Database Migrations & Superuser Creation

Run Django migrations to initialize all database tables, constraints, and indexes, then create an administrator account:

```bash
python manage.py makemigrations jobs
python manage.py migrate
python manage.py createsuperuser
```
*(Follow the interactive prompts to set your admin username, email, and password).*

---

## Running & Verifying the Application

### 1. Start the Development Server
```bash
python manage.py runserver
```

### 2. Verify via the Modern Web Interface
1. Open your browser and navigate to: **`http://127.0.0.1:8000/`**
2. Log in using your superuser credentials (or register a new user at `http://127.0.0.1:8000/register/`).
3. Navigate to **Search Queries** (`http://127.0.0.1:8000/queries/`).
4. In the **"Create New Query"** form, enter:
   * **Keyword**: `Python Developer` (or `Golang Engineer`, `Django Developer`)
   * **Country or City**: `USA` (or `Germany`, `Poland`, etc.)
   * Click **Add Query**.
5. Click the **"Scrape in 1-Click"** button next to your query.
   * This launches a background worker running **Phase 1 (Search)** followed immediately by **Phase 2 (Details)**.
6. Navigate back to the **Jobs** tab (`http://127.0.0.1:8000/`):
   * Postings populate the grid within 15–30 seconds.
   * Use the search input and status dropdown (`Detailed`, `Pending`, `Failed`) to filter records.
   * Click **"View Details"** on any card to read the complete job description, metadata tags, and the direct **"Apply on LinkedIn"** button.
   * Click **"Export CSV"** to immediately download the current filtered dataset to your machine.

---

### 3. Verify via the Django Admin Panel
1. Navigate to: **`http://127.0.0.1:8000/admin/`**
2. **Search Queries Section (`/admin/jobs/searchquery/`)**:
   * Add, edit, or toggle `is_active` and `max_pages` inline.
   * Select queries, open the **Action** dropdown, and trigger:
     * `⚡ Run Search Scraper for selected queries (Stage 1)`
     * `🚀 Run Full Scrape Pipeline (Search + Details)`
3. **Jobs Section (`/admin/jobs/job/`)**:
   * Inspect collected vacancies and filter by `status`, `employment_type`, `seniority_level`, or `search_query`.
   * Select jobs and use the **Action** dropdown to export:
     * `Export selected jobs to CSV`
     * `Export selected jobs to Excel (.xlsx)`

---

## Independent CLI Commands

All scraping, maintenance, and export workflows can be executed independently from the terminal:

### Phase 1: Search Scraper
Fetches job cards for active `SearchQuery` records and saves them with `Pending` status:
```bash
# Run for all active SearchQuery records
python manage.py scrape_search

# Or target a specific SearchQuery by ID
python manage.py scrape_search --query-id 1
```

### Phase 2: Details Scraper
Fetches full descriptions, criteria, and apply links for `Pending` records and marks them `Detailed`:
```bash
# Process up to 1,000 Pending jobs
python manage.py scrape_details --limit 1000

# Retry previously failed jobs (retry_count < 3)
python manage.py scrape_details --limit 500 --retry-failed
```

### Export Jobs via CLI
Export jobs directly to spreadsheet files:
```bash
# Export Detailed jobs to Excel (.xlsx)
python manage.py export_jobs --output detailed_jobs.xlsx

# Export Detailed jobs to CSV (.csv)
python manage.py export_jobs --output detailed_jobs.csv

# Export jobs across all statuses (Pending, Detailed, Failed)
python manage.py export_jobs --output all_jobs.xlsx --all-statuses
```

### Database Cleanup Utilities
Manage and clean up scraped database records:
```bash
# Delete all scraped jobs (keeps SearchQuery records intact)
python manage.py clear_jobs

# Delete only Failed jobs
python manage.py clear_jobs --failed-only

# Delete both Jobs and SearchQuery records
python manage.py clear_jobs --all
```

---

## Logging & Monitoring

All scraper network events, pagination offsets, rate-limit backoffs (`HTTP 429`), and exceptions are recorded in real time to both console output and `scraper.log`:

```bash
tail -f scraper.log
```
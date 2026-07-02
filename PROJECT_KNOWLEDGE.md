# FairHire — Complete Project Knowledge Base

> **Purpose of this document:** A self-contained reference that lets any engineer fully understand, explain, maintain, or extend FairHire without needing access to the original codebase. Last updated after migration 0006 and the addition of the FastAPI microservice (`api.py`).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [Project Architecture](#3-project-architecture)
4. [Folder Structure](#4-folder-structure)
5. [Frontend Analysis](#5-frontend-analysis)
6. [Backend Analysis](#6-backend-analysis)
7. [Database Documentation](#7-database-documentation)
8. [API Documentation](#8-api-documentation)
9. [Authentication & Security](#9-authentication--security)
10. [Important Algorithms & Logic](#10-important-algorithms--logic)
11. [Complete User Journey](#11-complete-user-journey)
12. [Interview Preparation Notes](#12-interview-preparation-notes)
13. [Common Bugs & Debugging Guide](#13-common-bugs--debugging-guide)
14. [Future Improvements](#14-future-improvements)
15. [Project Explanation Scripts](#15-project-explanation-scripts)

---

## 1. Executive Summary

### Project Name
**FairHire**

### Purpose
FairHire is an AI-assisted recruitment platform that combines a traditional job board with automated resume parsing, candidate–job match scoring, and bias detection — both in job descriptions (before posting) and in hiring criteria (during evaluation). It also ships a standalone **FastAPI microservice** (`api.py`) that exposes the AI utilities as pure JSON REST endpoints, decoupled from Django entirely.

### Problem Being Solved
Traditional recruitment suffers from two intertwined problems:
1. **Inefficiency** — HR teams manually review hundreds of unranked resumes with no objective scoring.
2. **Bias** — Hiring decisions are influenced by irrelevant factors (gender, college prestige, age-coded language in job descriptions).

FairHire addresses both: it automates the ranking of applicants by fit score while surfacing hidden bias so HR can make informed, equitable decisions.

### Target Users

| Role | Description |
|------|-------------|
| **HR / Recruiter** | Posts jobs, reviews ranked applicants, defines hiring criteria, schedules interviews, reads analytics |
| **Candidate / Job Seeker** | Browses public job board, applies, uploads resume for AI parsing, tracks application status |
| **Platform Admin** | Uses Django's `/admin` panel to manage all records |
| **API Consumer** | External services that call `api.py` for resume parsing, scoring, or bias detection without Django |

### Key Features
1. Dual-role authentication (HR and Candidate sign-up flows)
2. Public job board with search and filter
3. AI resume parsing — extracts skills, experience years, education from PDF/DOCX
4. Candidate–job match scoring (0–100, skill overlap + TF-IDF cosine similarity)
5. Skill gap analysis per application
6. HR-defined bias criteria evaluated automatically on every application
7. Job description bias detector — flags gendered, ageist, ableist language before publishing
8. Blind review mode — hides candidate demographics during review
9. Interview scheduling — HR proposes slots, candidate picks one, others auto-cancelled
10. In-app messaging thread per application
11. Real-time notification bell with unread count
12. Calendar export (`.ics`) for booked interview events
13. HR analytics dashboard — per-job funnel (applied → shortlisted → interview → hired)
14. CSV export of applicants
15. **FastAPI microservice** (`api.py`) — REST wrapper around all four AI utility modules

---

## 2. Technology Stack

### Django App (Primary Server)

| Layer | Technology | Version |
|-------|-----------|---------|
| Web Framework | Django | 5.0.6 |
| Language | Python | 3.11+ |
| Database | SQLite3 | file: `db.sqlite3` |
| ORM | Django ORM | built-in |
| Config | python-decouple | 3.8 |
| Email (dev) | Django console backend | built-in |

### FastAPI Microservice (`api.py`)

| Component | Technology | Version |
|-----------|-----------|---------|
| API Framework | FastAPI | 0.111+ |
| ASGI Server | uvicorn | 0.29+ |
| Validation | Pydantic v2 | (FastAPI dependency) |
| File upload | Python `tempfile` + `base64` | built-in |

### AI / NLP Libraries (shared by both servers)

| Library | Version | Purpose |
|---------|---------|---------|
| PyMuPDF (`fitz`) | 1.27.1 | Extract text from PDF resumes |
| python-docx | 1.2.0 | Extract text from DOCX resumes |
| scikit-learn | 1.8.0 | TF-IDF vectoriser + cosine similarity |
| NumPy | 2.4.2 | Numerical support for sklearn |
| SciPy | 1.17.1 | Sparse matrix support |
| spaCy + `en_core_web_sm` | 3.8.11 | Installed, reserved for future NLP use |

### Frontend

| Component | Technology |
|-----------|-----------|
| Templating | Django Templates |
| CSS | Vanilla CSS (embedded in `base.html`) |
| Typography | Google Fonts — Inter |
| JavaScript | **None** — zero JS dependencies |

### Infrastructure / DevOps

| Component | Technology |
|-----------|-----------|
| Containerisation | Docker (Dockerfile provided) |
| Static files | Django `staticfiles` |
| Media files | Local filesystem (`/media/`) |

---

## 3. Project Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Browser / API Client                      │
│                   HTML forms (no JS)  OR  JSON (REST)               │
└────────────────────────┬────────────────────────┬───────────────────┘
                         │ HTTP :8000              │ HTTP :8001
                         ▼                         ▼
          ┌──────────────────────┐   ┌──────────────────────────┐
          │   Django Dev Server  │   │  FastAPI (uvicorn)       │
          │                      │   │  api.py                  │
          │  FairHire/urls.py    │   │  /parse-resume           │
          │  recruitment/urls.py │   │  /score-match            │
          │  views.py            │   │  /evaluate-bias          │
          │  forms.py            │   │  /detect-bias            │
          │  models.py (ORM)     │   │  (no DB access)          │
          └──────────┬───────────┘   └──────────┬───────────────┘
                     │                           │
                     │         ┌─────────────────┘
                     │         │  shared pure-Python modules
                     ▼         ▼
          ┌────────────────────────────────────┐
          │     recruitment/utils/             │
          │   ├─ resume_parser.py              │
          │   ├─ match_scorer.py               │
          │   ├─ bias_agent.py                 │
          │   └─ bias_detector.py              │
          └──────────────────────────────────┬─┘
                                             │ (Django only)
                                             ▼
                                  ┌──────────────────┐
                                  │   db.sqlite3     │
                                  │  (11 tables)     │
                                  └──────────────────┘
```

**Key architectural insight:** The four utility modules have **zero Django dependencies at module load time**. This is why `api.py` can import them directly without configuring Django — all Django ORM calls are either inside function bodies with lazy imports, or inside `run_bias_agent()` which `api.py` deliberately does not call.

### Data Flow — Application Submission (Django)

```
Candidate clicks "Apply"
        │
        ▼
job_apply() view
        │
        ├─► Save JobApplication to DB (always)
        │
        ├─► [best-effort] Compute match score
        │       ├─ score_skills_overlap()   → 0-100 (70% weight)
        │       └─ score_text_similarity()  → 0-100 (30% weight)
        │       └─ Save ApplicationMatchScore to DB
        │
        ├─► [best-effort] Run bias agent
        │       └─ evaluate each JobBiasCriteria → pass/fail
        │       └─ Save ApplicationBiasResult per criterion
        │
        ├─► Create Notifications (HR + Candidate)
        │
        └─► Send email (console backend in dev, fail_silently=True)
```

### Data Flow — FastAPI Request

```
POST /parse-resume
        │
        ▼
Decode base64 → write temp file (.pdf/.docx)
        │
        ▼
parse_resume(tmp_path)    ← resume_parser.py
        │
        ▼
Delete temp file (always, in finally block)
        │
        ▼
Return JSON: {skills, experience_years, education, raw_text}
```

### Request–Response Flow (Django)

```
GET  /jobs/          →  job_list view  →  ORM query  →  job_list.html
POST /jobs/5/apply/  →  job_apply view →  form valid  →  DB writes × 3
                                       →  redirect    →  /candidate/applications/
```

### Component Interaction Map

```
views.py
  ├── forms.py          (validation)
  ├── models.py         (ORM)
  ├── utils/resume_parser.py     (called by parse_resume_view)
  ├── utils/match_scorer.py      (called by job_apply, applicant_list, job_list)
  ├── utils/bias_agent.py        (called by job_apply, run_bias_check_view)
  └── utils/bias_detector.py    (called by job_create, job_edit)

api.py (FastAPI — no Django, no DB)
  ├── utils/resume_parser.py     → parse_resume()
  ├── utils/match_scorer.py      → score_skills_overlap(), score_text_similarity(), analyze_skill_gap()
  ├── utils/bias_agent.py        → _EVALUATORS dict only (not run_bias_agent)
  └── utils/bias_detector.py    → scan_job_description()

context_processors.py
  └── injects notifications_unread count into every template context

base.html
  └── extended by all 21 templates via {% extends "base.html" %}
```

---

## 4. Folder Structure

```
Recruiting/                              ← Project root / git repo root
│
├── manage.py                            ← Django CLI entry point
├── requirements.txt                     ← All Python dependencies (Django + AI libs)
├── requirements_api.txt                 ← Additional deps for api.py (fastapi, uvicorn)
├── api.py                               ← FastAPI microservice (standalone, port 8001)
├── dockerfile                           ← Docker container for Django app
├── .env                                 ← SECRET_KEY, DEBUG, ALLOWED_HOSTS (not committed)
├── .gitignore
├── db.sqlite3                           ← SQLite database (all 11 tables)
├── docs.md                              ← Original developer notes
├── PROJECT_KNOWLEDGE.md                 ← This document
│
├── FairHire/                            ← Django project package
│   ├── settings.py                      ← All Django configuration
│   ├── urls.py                          ← Root URL router → delegates to recruitment.urls
│   ├── wsgi.py                          ← WSGI entry point
│   └── asgi.py                          ← ASGI entry point (not configured)
│
├── recruitment/                         ← Single Django app (all application logic)
│   ├── models.py                        ← 11 database models
│   ├── views.py                         ← 25+ view functions/classes
│   ├── urls.py                          ← 30 URL patterns
│   ├── forms.py                         ← 9 form classes + 1 inline formset
│   ├── admin.py                         ← Django admin registrations (9 models)
│   ├── context_processors.py            ← Injects notifications_unread into all templates
│   ├── apps.py                          ← AppConfig
│   ├── tests.py                         ← Placeholder (no tests written)
│   │
│   ├── utils/                           ← Pure Python business logic (no Django deps)
│   │   ├── resume_parser.py             ← PDF/DOCX text extraction + skill/exp/edu parsing
│   │   ├── match_scorer.py              ← Skill overlap + TF-IDF cosine similarity scoring
│   │   ├── bias_agent.py                ← Evaluates candidates against HR bias criteria
│   │   └── bias_detector.py            ← Scans job descriptions for biased language
│   │
│   ├── migrations/                      ← Django migration history
│   │   ├── 0001_initial.py              ← CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication
│   │   ├── 0002_...                     ← Email uniqueness + profile tweaks
│   │   ├── 0003_...                     ← ResumeParseResult, ApplicationMatchScore
│   │   ├── 0004_...                     ← CandidateProfile.gender, JobBiasCriteria, ApplicationBiasResult
│   │   ├── 0005_...                     ← InterviewSlot, Message, Notification
│   │   └── 0006_...                     ← Explicit AutoField PKs (Django 5 compatibility fix)
│   │
│   └── templates/
│       ├── base.html                    ← Master layout: CSS design system, nav, flash messages
│       ├── registration/
│       │   ├── login.html
│       │   └── signup_form.html         ← Shared for HR and Candidate (user_type context var)
│       └── recruitment/                 ← 19 feature templates (see Section 5)
│
├── media/                               ← User-uploaded files (not committed)
│   ├── resumes/                         ← Candidate profile resumes
│   └── application_resumes/             ← Per-application resume snapshots
│
├── static/                              ← Static assets directory (currently empty)
└── venv/                                ← Python virtual environment (not committed)
```

### Key File Dependency Map

| File | Depends On | Used By |
|------|-----------|---------|
| `models.py` | Django ORM, `django.conf.settings` | `views.py`, `admin.py`, `forms.py`, utils (via lazy imports) |
| `views.py` | `models.py`, `forms.py`, all 4 utils | `urls.py` |
| `forms.py` | `models.py` | `views.py` |
| `utils/resume_parser.py` | `os`, `re`; lazy: PyMuPDF, python-docx | `views.parse_resume_view`, `api.py /parse-resume` |
| `utils/match_scorer.py` | `re`; lazy: scikit-learn | `views.job_apply`, `views.applicant_list`, `views.job_list`, `api.py /score-match` |
| `utils/bias_agent.py` | nothing at load time; lazy: `recruitment.models` | `views.job_apply`, `views.run_bias_check_view`, `api.py /evaluate-bias` (partial) |
| `utils/bias_detector.py` | `re` | `views.job_create`, `views.job_edit`, `api.py /detect-bias` |
| `api.py` | FastAPI, Pydantic, all 4 utils (direct) | standalone process |
| `context_processors.py` | `models.Notification` | every template (via `settings.py`) |

### Migration 0006 — What and Why

Migration 0006 (`0006_alter_applicationbiasresult_id_and_more.py`) performs no data or schema changes — it only explicitly sets the `id` field on all 11 models to `AutoField` (32-bit integer PK). **Why:** Django 5 changed `DEFAULT_AUTO_FIELD` to `BigAutoField` (64-bit). The original models were written against the implicit 32-bit default, so Django's migration detector flagged a mismatch. The fix makes the PK type explicit so future `makemigrations` runs stay clean.

---

## 5. Frontend Analysis

### Design System (`base.html`)

All CSS lives in a single `<style>` block in `base.html` using CSS custom properties:

```css
:root {
  --primary:    #6366f1;   /* indigo  — buttons, brand, active links */
  --secondary:  #10b981;   /* emerald — success, hired badge */
  --danger:     #ef4444;   /* red     — errors, rejected badge */
  --warning:    #f59e0b;   /* amber   — shortlisted, warnings */
}
```

**No JavaScript framework. No CSS framework.** Pure hand-written vanilla CSS with CSS Grid, Flexbox, and CSS transitions. This makes the project extremely portable but limits interactivity to what server-side rendering can provide.

### All Pages and Templates

| Template | URL | Access | Purpose |
|----------|-----|--------|---------|
| `home.html` | `/` | Public | Landing page with live stats (open jobs, total candidates, applications) |
| `login.html` | `/login/` | Public | Username + password login form |
| `signup_form.html` | `/signup/hr/` or `/signup/candidate/` | Public | Shared sign-up form; `user_type` context var changes the heading |
| `job_list.html` | `/jobs/` | Public | Job card grid; search/filter bar; match % badge for logged-in candidates |
| `job_detail.html` | `/jobs/<pk>/` | Public | Full job description + Apply button |
| `job_apply.html` | `/jobs/<pk>/apply/` | Candidate | Cover letter + optional resume upload |
| `hr_dashboard.html` | `/hr/dashboard/` | HR | Stat cards, job table, upcoming interviews, notification bell |
| `hr_profile.html` | `/hr/profile/` | HR | Company info, logo, contact details edit form |
| `job_form.html` | `/hr/jobs/new/` or `edit/` | HR | Job create/edit + inline bias criteria rows (up to 5) |
| `job_confirm_delete.html` | `/hr/jobs/<pk>/delete/` | HR | Confirm before deletion |
| `applicant_list.html` | `/hr/jobs/<pk>/applicants/` | HR | Table: match score (color-coded), bias grid, blind-mode toggle |
| `application_status_form.html` | `/hr/applications/<pk>/status/` | HR | Status dropdown + internal notes |
| `hr_analytics.html` | `/hr/analytics/` | HR | Per-job funnel table with rates |
| `candidate_dashboard.html` | `/candidate/dashboard/` | Candidate | Application counts by status, upcoming interviews, parse-resume CTA |
| `candidate_profile.html` | `/candidate/profile/` | Candidate | Bio, skills, experience, resume upload, social links |
| `my_applications.html` | `/candidate/applications/` | Candidate | Applications + match score + missing skills per job |
| `interview_propose.html` | `/hr/applications/<pk>/interview/propose/` | HR | Up to 3 datetime-local slot pickers |
| `interview_select.html` | `/candidate/applications/<pk>/interview/` | Candidate | Proposed slots list; pick one to book |
| `messages.html` | `/messages/<pk>/` | HR or Candidate | Chronological message thread per application |
| `notifications.html` | `/notifications/` | Auth | Full notification list; marks all read on load |

### Routing
All routing is server-side. Every navigation is a standard `<a>` anchor or form POST. No AJAX, no SPA routing, no client-side router.

### State Management
All state lives in SQLite. Django session cookie (`sessionid`) maintains authentication state. Django `messages` framework (cookie/session-backed) provides one-shot flash banners after form submission.

### User Flow

```
[Public]
  Landing (/)
    ├── Browse Jobs → Job Detail → Apply (redirects to login if needed)
    ├── Login → HR Dashboard or Candidate Dashboard
    └── Sign Up (HR or Candidate)

[HR]
  Dashboard → Post Job → Applicant List → Update Status
                                        → Propose Interview
                                        → Message Candidate
           → Analytics
           → Profile Edit

[Candidate]
  Dashboard → Browse & Apply
           → Parse Resume (POST button)
           → My Applications → Pick Interview Slot
           → Profile Edit
           → Messages
```

### Important UI Logic

**Blind Review Mode**: `?blind=1` URL parameter sets `blind_mode=True` in context. The template conditionally renders candidate name, email, and gender only when `blind_mode` is False. Server-side — no JS required.

**Notification Bell**: `context_processors.py` injects `notifications_unread` count into every request. The `<header>` in `base.html` renders a red pill over the bell icon when count > 0.

**Match Score Color Coding**: `ApplicationMatchScore.score_color()` returns one of three hex values — `#10b981` (green ≥70), `#f59e0b` (amber 40–69), `#ef4444` (red <40). Applied as inline `style="color: ..."` in templates.

---

## 6. Backend Analysis

### Server Setup
- **Entry**: `python manage.py runserver` (dev) or WSGI via `FairHire/wsgi.py` (prod)
- **Root URL conf**: `FairHire/urls.py` → delegates everything except `/admin/` to `recruitment/urls.py`
- **Single app**: `recruitment` (all models, views, forms, utils)

### Custom Decorators (`views.py:33–52`)

```python
@hr_required        # @login_required + user.is_hr check
@candidate_required # @login_required + user.is_candidate check
```

Both redirect to `home` with an error message on failure.

### View Architecture
- **Class-Based Views (CBVs)**: auth flows — `HRSignUpView`, `CandidateSignUpView` (extend `CreateView`), `CustomLoginView` (extends `LoginView`)
- **Function-Based Views (FBVs)**: all feature views — simpler for a single-app monolith

### Key View Logic

**`applicant_list`** (most complex view):
1. Queries applications with `select_related` + `prefetch_related` for performance
2. Backfills missing match scores for old applications
3. Backfills missing bias results if criteria count > result count
4. Deduplicates skills from manual profile + parsed resume, computes top-3 display
5. Builds `{app.pk: {criterion.pk: result_or_None}}` nested dict for grid rendering
6. Supports `?blind=1` mode

**`job_apply`** (triggers all AI pipeline):
1. Saves `JobApplication` — this always succeeds
2. Computes and saves `ApplicationMatchScore` — best-effort, `try/except` around all
3. Runs bias agent, saves `ApplicationBiasResult` per criterion — best-effort
4. Creates `Notification` for HR and candidate
5. Sends email (console backend, `fail_silently=True`)

**`parse_resume_view`**: POST-only. Calls `parse_resume(profile.resume.path)` → saves `ResumeParseResult` → merges parsed skills into profile (union, case-insensitive) → backfills experience_years and education if not set.

**`slot_ics`**: Generates RFC 5545-compliant `.ics` string inline (no library). Converts times to UTC with `Z` suffix. Returns `Content-Disposition: attachment` for browser download.

### Middleware Stack (in order)
1. `SecurityMiddleware` — HTTPS headers
2. `SessionMiddleware` — session cookie management
3. `CommonMiddleware` — URL normalisation
4. `CsrfViewMiddleware` — CSRF token validation on all POSTs
5. `AuthenticationMiddleware` — attaches `request.user`
6. `MessageMiddleware` — flash messages
7. `XFrameOptionsMiddleware` — `X-Frame-Options: DENY`

### Business Rules Enforced in Code
| Rule | Where enforced |
|------|---------------|
| One application per candidate per job | `unique_together = ('job', 'candidate')` on `JobApplication` |
| HR can only manage their own jobs | `get_object_or_404(JobPosting, pk=pk, posted_by=request.user)` |
| Candidate can only book their own slots | `get_object_or_404(InterviewSlot, application__candidate=request.user)` |
| Messages only for parties on the application | Manual `if` check in `message_thread` view |
| All AI scoring is non-blocking | Every AI call wrapped in `try/except` with `pass` on failure |

---

## 7. Database Documentation

### All 11 Tables

#### `recruitment_customuser` (extends Django auth_user)
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK (AutoField) | |
| `username` | VARCHAR(150) | UNIQUE | |
| `email` | VARCHAR(254) | UNIQUE | Custom — Django default is not unique |
| `password` | VARCHAR(128) | | bcrypt/PBKDF2 hash |
| `is_hr` | BOOLEAN | | DEFAULT False |
| `is_candidate` | BOOLEAN | | DEFAULT False |
| `first_name` | VARCHAR(150) | | |
| `last_name` | VARCHAR(150) | | |
| `is_active` | BOOLEAN | | DEFAULT True |
| `is_staff` | BOOLEAN | | DEFAULT False |
| `date_joined` | DATETIME | | |

#### `recruitment_hrprofile`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | FK→customuser, UNIQUE | CASCADE, OneToOne |
| `company_name` | VARCHAR(200) | | |
| `department` | VARCHAR(200) | | |
| `phone` | VARCHAR(20) | | |
| `company_logo` | VARCHAR(100) | | nullable, upload_to='company_logos/' |
| `company_website` | VARCHAR(200) | | URL |
| `company_description` | TEXT | | |

#### `recruitment_candidateprofile`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | FK→customuser, UNIQUE | CASCADE, OneToOne |
| `bio` | TEXT | | |
| `skills` | TEXT | | Comma-separated, e.g. "Python, Django, SQL" |
| `experience_years` | INTEGER | | NOT NULL, DEFAULT 0 |
| `education` | VARCHAR(300) | | |
| `resume` | VARCHAR(100) | | nullable, upload_to='resumes/' |
| `linkedin_url` | VARCHAR(200) | | |
| `github_url` | VARCHAR(200) | | |
| `portfolio_url` | VARCHAR(200) | | |
| `gender` | VARCHAR(20) | | optional, used by bias agent |

#### `recruitment_jobposting`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `posted_by_id` | INTEGER | FK→customuser | CASCADE |
| `title` | VARCHAR(200) | | |
| `description` | TEXT | | |
| `required_skills` | TEXT | | Comma-separated |
| `location` | VARCHAR(200) | | |
| `location_type` | VARCHAR(10) | | CHOICES: remote/onsite/hybrid |
| `salary_min` | INTEGER | | nullable |
| `salary_max` | INTEGER | | nullable |
| `deadline` | DATE | | nullable |
| `status` | VARCHAR(10) | | CHOICES: open/closed/draft |
| `created_at` | DATETIME | | auto_now_add |
| `updated_at` | DATETIME | | auto_now |

#### `recruitment_jobapplication`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `job_id` | INTEGER | FK→jobposting | CASCADE |
| `candidate_id` | INTEGER | FK→customuser | CASCADE |
| `cover_letter` | TEXT | | |
| `resume_snapshot` | VARCHAR(100) | | nullable, upload_to='application_resumes/' |
| `status` | VARCHAR(15) | | CHOICES: applied/shortlisted/interview/hired/rejected/withdrawn |
| `applied_at` | DATETIME | | auto_now_add |
| `updated_at` | DATETIME | | auto_now |
| `hr_notes` | TEXT | | invisible to candidate |

**Constraint**: `UNIQUE(job_id, candidate_id)` — one application per candidate per job.

#### `recruitment_resumeparseresult`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `candidate_id` | INTEGER | FK→candidateprofile, UNIQUE | CASCADE, OneToOne |
| `raw_text` | TEXT | | full resume plain text |
| `parsed_skills` | TEXT | | comma-separated extracted skills |
| `parsed_experience_years` | INTEGER | | nullable |
| `parsed_education` | VARCHAR(400) | | |
| `parsed_at` | DATETIME | | auto_now |

#### `recruitment_applicationmatchscore`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `application_id` | INTEGER | FK→jobapplication, UNIQUE | CASCADE, OneToOne |
| `score` | SMALLINT | | 0–100 |
| `skill_overlap_pct` | FLOAT | | 0.0–100.0 |
| `text_similarity_pct` | FLOAT | | 0.0–100.0 |
| `computed_at` | DATETIME | | auto_now |

#### `recruitment_jobbiasCriteria`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `job_id` | INTEGER | FK→jobposting | CASCADE |
| `criterion` | VARCHAR(20) | | CHOICES: experience_min/college_tier/gender/custom |
| `value` | VARCHAR(200) | | e.g. "5+", "Tier 1", "Female" |
| `description` | VARCHAR(300) | | optional HR label |
| `created_at` | DATETIME | | auto_now_add |

#### `recruitment_applicationbiasresult`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `application_id` | INTEGER | FK→jobapplication | CASCADE |
| `criterion_id` | INTEGER | FK→jobbiasCriteria | CASCADE |
| `passed` | BOOLEAN | | NOT NULL |
| `detail` | VARCHAR(300) | | human-readable explanation |
| `evaluated_at` | DATETIME | | auto_now |

**Constraint**: `UNIQUE(application_id, criterion_id)` — one result per (application, criterion) pair. `update_or_create` used so re-runs replace old results.

#### `recruitment_notification`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | FK→customuser | CASCADE |
| `title` | VARCHAR(200) | | |
| `body` | TEXT | | |
| `link` | VARCHAR(300) | | relative URL |
| `unread` | BOOLEAN | | DEFAULT True |
| `created_at` | DATETIME | | auto_now_add |

#### `recruitment_interviewslot`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `application_id` | INTEGER | FK→jobapplication | CASCADE |
| `start_time` | DATETIME | | |
| `end_time` | DATETIME | | |
| `status` | VARCHAR(10) | | CHOICES: proposed/booked/cancelled |
| `proposed_by_id` | INTEGER | FK→customuser | CASCADE |
| `booked_by_id` | INTEGER | FK→customuser | SET_NULL, nullable |
| `created_at` | DATETIME | | auto_now_add |

#### `recruitment_message`
| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | INTEGER | PK | |
| `application_id` | INTEGER | FK→jobapplication | CASCADE |
| `sender_id` | INTEGER | FK→customuser | CASCADE |
| `text` | TEXT | | |
| `created_at` | DATETIME | | auto_now_add |

### Entity–Relationship Diagram

```
CustomUser
  │
  ├──[1:1]──► HRProfile
  │
  ├──[1:1]──► CandidateProfile ──[1:1]──► ResumeParseResult
  │
  ├──[FK posted_by]──► JobPosting
  │                         │
  │                         ├──[1:N]──► JobBiasCriteria ◄────────────┐
  │                         │                                         │
  │                         └──[1:N]──► JobApplication               │
  │                                          │                        │
  │                              ┌───────────┤                        │
  │                              │           │                        │
  │                         [1:1]▼      [1:N]▼                  [FK]▼
  │                    ApplicationMatchScore  ApplicationBiasResult
  │
  ├──[1:N]──► Notification
  │
  └──[FK proposed_by/booked_by]──► InterviewSlot ◄──[FK application]── JobApplication
                                                                            │
  CustomUser ──[FK sender]──► Message ◄──[FK application]─────────────────┘
```

### Example Records

```
CustomUser:  id=1, username='hr_techcorp', is_hr=True
JobPosting:  id=5, title='Senior Python Dev', required_skills='Python,Django,PostgreSQL,Docker'
JobApplication: id=12, job_id=5, candidate_id=7, status='shortlisted'
ApplicationMatchScore: id=12, application_id=12, score=78, skill_overlap_pct=85.7, text_similarity_pct=57.3
JobBiasCriteria: id=3, job_id=5, criterion='experience_min', value='3+'
ApplicationBiasResult: id=20, application_id=12, criterion_id=3, passed=True, detail='5 yr(s) ≥ required 3+ yr(s)'
```

---

## 8. API Documentation

### Part A — Django HTML Endpoints (30 routes)

All state-changing requests are HTML form POSTs with CSRF tokens. Responses are full HTML page renders or redirects.

#### Public Endpoints

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/` | GET | `home` | Landing page |
| `/login/` | GET, POST | `CustomLoginView` | Login |
| `/logout/` | POST | `LogoutView` | Logout → redirect home |
| `/signup/hr/` | GET, POST | `HRSignUpView` | HR registration |
| `/signup/candidate/` | GET, POST | `CandidateSignUpView` | Candidate registration |
| `/jobs/` | GET | `job_list` | Job board (`?q=`, `?location_type=`, `?skills=`) |
| `/jobs/<pk>/` | GET | `job_detail` | Job detail |

#### HR-Only Endpoints

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/hr/dashboard/` | GET | `hr_dashboard` | Overview |
| `/hr/analytics/` | GET | `hr_analytics` | Funnel table |
| `/hr/profile/` | GET, POST | `hr_profile_edit` | Company profile |
| `/hr/jobs/new/` | GET, POST | `job_create` | Create job + bias criteria |
| `/hr/jobs/<pk>/edit/` | GET, POST | `job_edit` | Edit job |
| `/hr/jobs/<pk>/delete/` | GET, POST | `job_delete` | Delete job |
| `/hr/jobs/<pk>/applicants/` | GET | `applicant_list` | All applicants (`?blind=1`) |
| `/hr/jobs/<pk>/bias-check/` | POST | `run_bias_check_view` | Re-run bias agent for all applicants |
| `/hr/jobs/<pk>/export.csv` | GET | `export_applicants_csv` | Download CSV |
| `/hr/analytics/` | GET | `hr_analytics` | Analytics |
| `/hr/applications/<pk>/status/` | GET, POST | `application_update_status` | Change status |
| `/hr/applications/<pk>/interview/propose/` | GET, POST | `propose_interview` | Propose interview slots |

#### Candidate-Only Endpoints

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/candidate/dashboard/` | GET | `candidate_dashboard` | Overview |
| `/candidate/profile/` | GET, POST | `candidate_profile_edit` | Edit profile |
| `/candidate/applications/` | GET | `my_applications` | Applications + skill gaps |
| `/candidate/parse-resume/` | POST | `parse_resume_view` | Trigger AI resume parsing |
| `/jobs/<pk>/apply/` | GET, POST | `job_apply` | Apply to job |
| `/candidate/applications/<pk>/interview/` | GET | `candidate_interview_select` | View proposed slots |
| `/candidate/slots/<slot_id>/book/` | POST | `book_interview_slot` | Book a slot |

#### Shared Auth Endpoints

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/notifications/` | GET | `notifications_list` | View + mark-all-read |
| `/messages/<pk>/` | GET, POST | `message_thread` | Read/send messages |
| `/slots/<slot_id>/ics/` | GET | `slot_ics` | Download `.ics` calendar event |

---

### Part B — FastAPI JSON Endpoints (`api.py`, port 8001)

Interactive docs: **http://127.0.0.1:8001/docs**

#### `POST /parse-resume`

**Purpose**: Extract structured data from a PDF or DOCX resume.

**Request body**:
```json
{
  "filename": "john_doe_resume.pdf",
  "content_base64": "JVBERi0xLjQ..."
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `filename` | string | yes | Used for extension detection only (`.pdf`, `.docx`, `.doc`) |
| `content_base64` | string | yes | Standard base64 encoding of raw file bytes |

**Response `200`**:
```json
{
  "skills": ["Python", "Django", "Machine Learning"],
  "experience_years": 4,
  "education": "B.Tech CSE, IIT Delhi 2020",
  "raw_text": "John Doe\nSoftware Engineer\n..."
}
```

**Errors**:
- `422` — invalid base64 or unsupported file type
- `500` — parsing library failure

**Internal flow**: decode base64 → `NamedTemporaryFile(suffix=ext)` → `parse_resume(tmp_path)` → `finally: tmp_path.unlink()`

---

#### `POST /score-match`

**Purpose**: Compute a 0–100 candidate–job fit score.

**Request body**:
```json
{
  "candidate_skills": ["Python", "Django", "SQL", "Docker"],
  "required_skills": ["Python", "React", "SQL", "AWS"],
  "candidate_text": "Full resume raw text...",
  "job_text": "Senior Python Developer at TechCorp..."
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `candidate_skills` | string[] | yes | Combine profile skills + parsed skills for best accuracy |
| `required_skills` | string[] | yes | From `JobPosting.required_skills` comma-split |
| `candidate_text` | string | no | Resume raw text from `/parse-resume`; empty disables TF-IDF component |
| `job_text` | string | no | `job.title + job.description + job.required_skills`; empty disables TF-IDF |

**Response `200`**:
```json
{
  "composite_score": 62,
  "skill_overlap_pct": 50.0,
  "text_similarity_pct": 38.5,
  "skill_gap": ["React", "AWS"],
  "score_label": "Moderate"
}
```

**Score formula**: `composite = round(skill_overlap_pct × 0.70 + text_similarity_pct × 0.30)`
**Labels**: `"Strong"` ≥70 · `"Moderate"` 40–69 · `"Weak"` <40

---

#### `POST /evaluate-bias`

**Purpose**: Evaluate a candidate against one or more HR-defined hiring criteria.

**Request body**:
```json
{
  "candidate": {
    "experience_years": 4,
    "education": "B.Tech CSE, IIT Delhi",
    "gender": "Male",
    "bio": "Experienced backend engineer...",
    "skills": "Python, Django, Docker",
    "parsed_education": "B.Tech Computer Science",
    "parsed_experience_years": 5,
    "raw_text": "Full resume text..."
  },
  "criteria": [
    { "criterion": "experience_min", "value": "3+" },
    { "criterion": "college_tier",   "value": "Tier 1" },
    { "criterion": "gender",         "value": "Female" },
    { "criterion": "custom",         "value": "open source" }
  ]
}
```

**Candidate fields** (all optional except structurally required by the JSON):

| Field | Used by |
|-------|---------|
| `experience_years` | `experience_min` evaluator |
| `education` | `college_tier`, `custom` evaluators |
| `gender` | `gender` evaluator |
| `bio`, `skills` | `custom` evaluator |
| `parsed_education`, `raw_text` | `college_tier`, `custom` (fallback sources) |
| `parsed_experience_years` | `experience_min` (wins if higher than `experience_years`) |

**Criterion value formats**:

| Criterion | Value examples |
|-----------|---------------|
| `experience_min` | `"3"`, `"5+"`, `"2-4"` |
| `college_tier` | `"Tier 1"`, `"Tier 2"`, `"1"`, `"2"` |
| `gender` | `"Male"`, `"Female"`, `"any"` |
| `custom` | any keyword/phrase |

**Response `200`**:
```json
{
  "results": [
    { "criterion": "experience_min", "value": "3+", "passed": true,  "detail": "5 yr(s) ≥ required 3+ yr(s)" },
    { "criterion": "college_tier",   "value": "Tier 1", "passed": true,  "detail": "Detected 'iit' → qualifies as Tier 1" },
    { "criterion": "gender",         "value": "Female", "passed": false, "detail": "Gender 'Male' does not match preferred 'Female'" },
    { "criterion": "custom",         "value": "open source", "passed": false, "detail": "Keyword 'open source' not found in candidate profile" }
  ],
  "passed_count": 2,
  "failed_count": 2
}
```

**Errors**:
- `422` — unknown criterion type (validated before evaluation)

---

#### `POST /detect-bias`

**Purpose**: Scan a job description for potentially biased language.

**Request body**:
```json
{
  "text": "We need a rockstar ninja developer who can dominate the market."
}
```

**Response `200`**:
```json
{
  "warnings": [
    "Found potentially biased terms ('ninja', 'rockstar', 'dominate'): Strongly masculine-coded words can deter female applicants. Try: \"expert\", \"specialist\", \"driven\", or \"succeed\"."
  ],
  "is_clean": false,
  "warning_count": 1
}
```

Empty `text` → `warnings: [], is_clean: true, warning_count: 0` (no error).

**Lexicon categories scanned**:

| Category | Example terms |
|----------|--------------|
| `gendered_masculine` | ninja, rockstar, dominate, aggressive, guru |
| `gendered_feminine` | nurturing, empathetic, compassionate |
| `ageist` | digital native, young, recent grad, mature |
| `exclusionary_ableist` | normal, healthy, able-bodied, crazy |

---

## 9. Authentication & Security

### Login Flow

```
POST /login/ (username + password + CSRF token)
  → CustomLoginView validates credentials (Django auth backend)
  → get_success_url() checks user.is_hr or user.is_candidate
  → HR     → /hr/dashboard/
  → Candidate → /candidate/dashboard/
  → Other  → /
  → Session cookie set (sessionid, HttpOnly, 2-week default)
```

### Sign-Up Flow

```
HR Sign-Up:
  POST /signup/hr/ → HRSignUpForm.save()
    → user.is_hr = True
    → CustomUser.save()
    → HRProfile.objects.create(user=user)
    → login(request, user)   ← immediate auto-login
    → redirect /hr/dashboard/

Candidate: identical, sets is_candidate=True, creates CandidateProfile
```

### Session Handling
- Backend: database-backed sessions (`django.contrib.sessions`)
- Session ID in `sessionid` cookie (HttpOnly)
- Session data in `django_session` table
- Default lifetime: 2 weeks

### Authorization Rules

| Resource | Rule | Implementation |
|----------|------|----------------|
| HR views | `is_hr == True` | `@hr_required` decorator |
| Candidate views | `is_candidate == True` | `@candidate_required` decorator |
| Job applicant list | HR must be the poster | `get_object_or_404(JobPosting, pk=pk, posted_by=request.user)` |
| Interview slot booking | Must be candidate on that application | `get_object_or_404(InterviewSlot, application__candidate=request.user)` |
| Message threads | HR poster or candidate applicant | Manual `if` check in view |
| Admin panel | `is_staff == True` | Django built-in |

### CSRF Protection
All POST forms include `{% csrf_token %}`. `CsrfViewMiddleware` validates on every state-changing request — 403 on failure.

### Password Security (Django built-in validators)
- `UserAttributeSimilarityValidator` — password can't match username/email
- `MinimumLengthValidator` — minimum 8 characters
- `CommonPasswordValidator` — rejects 20,000 common passwords
- `NumericPasswordValidator` — can't be entirely numeric
- Stored as PBKDF2/SHA256 hashes

### FastAPI Security
`api.py` has **no authentication** — it is designed as an internal microservice. In production, place it behind a reverse proxy (Nginx) or API gateway with token validation.

### Known Security Gaps (Production Checklist)
1. `DEBUG = True` must be `False` in production
2. SQLite → PostgreSQL for concurrent access
3. No rate limiting on login (brute-force risk) — add `django-axes`
4. No file-type validation on resume uploads beyond extension check
5. `api.py` has no auth — restrict by network or add Bearer token middleware
6. HTTPS headers not set — add `SECURE_SSL_REDIRECT`, `HSTS_SECONDS`

---

## 10. Important Algorithms & Logic

### A. Resume Text Extraction (`resume_parser.py`)

Both heavy imports are **lazy** (inside the function body):
- **PDF**: `import fitz; doc = fitz.open(path); page.get_text()` per page, joined with `\n`
- **DOCX**: `from docx import Document; doc.paragraphs` joined with `\n`
- Returns empty string on any error — never raises

### B. Skill Detection (`resume_parser.py:_extract_skills`)

```
For each skill in SKILL_KEYWORDS (100+ terms):
    regex = r"\b" + re.escape(skill) + r"\b"   ← word boundary prevents substring matches
    if re.search(regex, text.lower()):
        add skill.title() to results
```

Whole-word regex prevents "r" matching inside "React" or "c" matching inside "science". Returns title-cased names (`"Machine Learning"` not `"machine learning"`).

### C. Experience Year Extraction (`resume_parser.py`)

```
Pattern: r"(\d+)\+?\s*(?:-\s*\d+\s*)?years?\s*(?:of\s*)?(?:experience|exp\.?|work)"
```

Captures: `"3 years experience"`, `"5+ years of work"`, `"2-4 years exp"`.
Returns the **maximum** number found in the document (a resume with "3 years X" and "2 years Y" → 3).

### D. Match Score — Skill Overlap (`match_scorer.py`)

**Formula**: `(matched / total_required) × 100`

- `matched` = `|candidate_skills_set ∩ required_skills_set|` (case-insensitive)
- This is a **recall** metric — what fraction of what the job needs does the candidate cover?
- A candidate covering 3/3 required skills scores 100 even with 20 other skills

### E. Match Score — Text Similarity (`match_scorer.py`)

```python
vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
tfidf = vectorizer.fit_transform([candidate_text, job_text])
score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100
```

**TF-IDF**: weights rare but meaningful terms higher than common words.
**Cosine similarity**: measures angle between document vectors — 0 = orthogonal (different), 1 = identical.
sklearn import is lazy (inside function body) — safe to import the module without sklearn installed.
Returns 0.0 if either text is empty.

### F. Composite Match Score

```
composite = round(skill_overlap × 0.70 + text_similarity × 0.30)
composite = min(100, max(0, composite))
```

**Why 70/30**: Skill overlap is objective and directly tied to requirements. Text similarity is a softer, noisier signal but catches domain experience not in the keyword list.

### G. Skill Gap Analysis (`match_scorer.py`)

Set difference: required skills that are NOT in the candidate's normalised skill set. Displayed in `my_applications.html` so candidates know what to learn.

### H. Bias Agent — Dispatch Table Pattern (`bias_agent.py`)

```python
_EVALUATORS = {
    'experience_min': evaluate_experience,
    'college_tier':   evaluate_college_tier,
    'gender':         evaluate_gender,
    'custom':         evaluate_custom,
}
```

Each evaluator: `(profile, value) → (passed: bool, detail: str)`. The dispatch table makes adding new criterion types a one-line change (add to dict).

**Experience evaluator** supports three value formats: `"5"` (min), `"5+"` (min), `"2-4"` (range inclusive). `parsed_experience_years` wins over `experience_years` when higher.

**College tier evaluator** uses two hard-coded keyword lists for Indian institutions:
- Tier 1: IIT, IIM, IISc, BITS Pilani, top NITs, IIIT Hyderabad, DTU, etc.
- Tier 2: All Tier 1 + other NITs, BITS campuses, regional engineering colleges
Searches the concatenation of `profile.education`, `parse_result.parsed_education`, and `parse_result.raw_text`.

**Custom evaluator**: case-insensitive substring search across bio + skills + education + gender + raw_text.

### I. `api.py` — Profile Duck-Typing with SimpleNamespace

`api.py` cannot use Django ORM objects. The bias-agent evaluators access `profile.education`, `profile.experience_years`, `profile.parse_result.raw_text`, etc. — all inside `try/except` blocks. `SimpleNamespace` satisfies these attribute accesses:

```python
profile = SimpleNamespace(
    experience_years=data.experience_years,
    education=data.education,
    gender=data.gender,
    bio=data.bio,
    skills=data.skills,
    parse_result=SimpleNamespace(
        parsed_education=data.parsed_education,
        parsed_experience_years=data.parsed_experience_years,
        raw_text=data.raw_text,
    ),
)
```

`run_bias_agent()` is deliberately NOT called from `api.py` — it lazy-imports `from recruitment.models import ApplicationBiasResult` and writes to the database. Instead `api.py` calls evaluators directly via `_EVALUATORS[criterion](profile, value)`.

### J. Interview Slot Booking (Atomic Cancel-Others Pattern)

```python
# Cancel all other proposed slots for this application in one UPDATE
InterviewSlot.objects.filter(
    application=application,
    status='proposed'
).exclude(pk=slot.pk).update(status='cancelled')

# Book the chosen slot
slot.status = 'booked'
slot.booked_by = request.user
slot.save()
```

Django wraps each ORM operation in a transaction. The bulk `.update()` and the `.save()` are effectively atomic at the SQLite level.

### K. Notification Deduplication (24-Hour Interview Reminders)

On every dashboard load, the view checks for booked slots within 24 hours and creates notifications — but only if a notification with the same `(user, title, link)` doesn't already exist:

```python
if not Notification.objects.filter(user=request.user, title=t, link=l).exists():
    Notification.objects.create(...)
```

This is a natural deduplication key. The cost is one extra `SELECT` per slot per dashboard load.

### L. Job Description Bias Detection (`bias_detector.py`)

Lexicon-based scanner. Four dictionaries of terms. For each category:
```python
re.search(r'\b' + re.escape(term) + r'\b', text.lower())
```
Word boundaries (`\b`) prevent `"stand"` from matching `"standard"`. Returns one warning string per triggered category, naming the matched terms and suggesting neutral alternatives.

---

## 11. Complete User Journey

### A. Opening the App

1. Browser loads `/`
2. `home` view queries: open job count, total candidates, total applications
3. `base.html` renders with sticky nav; unauthenticated users see Login + Sign Up buttons
4. Live stats appear in the hero section

### B. HR Signs Up and Posts a Job

1. `/signup/hr/` GET → `signup_form.html` with `user_type='HR'`
2. POST → `HRSignUpForm.save()` → `is_hr=True`, `CustomUser` + `HRProfile` created → `login(request, user)` → redirect `/hr/dashboard/`
3. HR clicks "+ Post Job" → `/hr/jobs/new/` → `job_form.html` with `JobPostingForm` + `JobBiasCriteriaFormSet` (1 empty row)
4. HR fills title, description, required skills, salary, deadline, location type; optionally adds bias criteria
5. POST: both forms validated atomically → job saved → bias criteria saved with `bias_formset.instance = job`
6. `scan_job_description(job.description)` runs → biased words → `messages.warning` banners
7. Redirect `/hr/dashboard/` with success flash

### C. Candidate Signs Up and Applies

1. Candidate visits `/jobs/` → browses card grid, searches/filters server-side
2. Clicks job → `/jobs/<pk>/` → full description + Apply button
3. If not logged in → redirected to login → sign up at `/signup/candidate/`
4. `CandidateSignUpForm.save()` → `is_candidate=True` → `CandidateProfile` created → auto-login → redirect `/candidate/dashboard/`
5. Navigates to `/jobs/<pk>/apply/` → fills cover letter, optionally uploads resume
6. POST:
   - `JobApplication` saved (status=`applied`)
   - Match score computed (`skill_pct × 0.70 + text_pct × 0.30`) → `ApplicationMatchScore` saved
   - Bias agent runs → `ApplicationBiasResult` per criterion saved
   - 2 notifications created (HR + candidate)
   - Email sent to console (dev)
7. Redirect `/candidate/applications/` with success flash

### D. Candidate Parses Resume

1. Candidate uploads PDF via `/candidate/profile/` → file saved to `media/resumes/`
2. Candidate clicks "Parse My Resume" on dashboard → POST `/candidate/parse-resume/`
3. `parse_resume(profile.resume.path)` → extract text → detect skills → infer years → detect education line
4. `ResumeParseResult.objects.update_or_create(candidate=profile, defaults={...})`
5. New skills merged into `profile.skills` (union, case-insensitive)
6. `experience_years`, `education` backfilled on profile if not set
7. Redirect dashboard with "Found N skills, X years of experience"

### E. HR Reviews Applicants

1. `/hr/jobs/<pk>/applicants/` → `applicant_list` view
2. Backfills match scores and bias results for any old applications
3. Deduplicates and computes display skills (top 3 + extra count)
4. Builds `bias_results_map = {app.pk: {criterion.pk: result_or_None}}`
5. Template: table with candidate name, skills, color-coded match score, bias grid (✅/❌ per criterion), status dropdown link
6. `?blind=1` hides name/email/gender
7. HR clicks "Update Status" → `/hr/applications/<pk>/status/` → status change → notification + console email to candidate

### F. Interview Scheduling

1. HR: "Propose Interview" → `InterviewProposeForm` → up to 3 datetime-local pairs
2. Validation: each pair needs start < end; at least 1 pair required
3. On submit: `InterviewSlot` records created (status=`proposed`) → notification + email to candidate
4. Candidate: notification → `/candidate/applications/<pk>/interview/` → list of proposed slots
5. Candidate clicks "Book This Slot" → POST `/candidate/slots/<slot_id>/book/`
6. All other `proposed` slots → `cancelled` in bulk UPDATE
7. Selected slot → `booked`, `booked_by = request.user`
8. HR notified; both see upcoming interview on dashboards
9. Either clicks download → `/slots/<slot_id>/ics/` → `.ics` file generated inline and downloaded

### G. Messaging

1. HR or candidate navigates to `/messages/<pk>/`
2. Authorization check: must be the HR who posted OR the candidate on the application
3. All messages shown chronologically (`ordering = ['created_at']`)
4. POST: `Message` created → `Notification` created for the other party → redirect (POST/Redirect/GET)

### H. Logging Out

1. POST to `/logout/` (form with `{% csrf_token %}`)
2. Django `LogoutView` invalidates session
3. Redirect to `/` via `next_page='home'`

---

## 12. Interview Preparation Notes

### Feature 1: Dual-Role Authentication

**Why**: HR and candidates have entirely different workflows and data. Two boolean flags on one `CustomUser` model is simpler than separate user tables or a Role FK table.

**Design decision**: Boolean flags (`is_hr`, `is_candidate`) rather than Django Groups — Groups work for permissions but don't cleanly handle role-specific profile data and separate dashboards.

**Alternatives considered**: Abstract user base class with HR and Candidate subclasses. Rejected — proxy models complicate cross-model queries.

**Interview questions**:
- "What if a user is both HR and candidate?" — Not prevented at DB level; sign-up forms set only one flag. Could add a model-level `clean()` validator.
- "Why not use Django's permission groups?" — Groups are great for many-to-many permissions; here we need profile data (HRProfile vs CandidateProfile) tied to the role, which boolean flags handle more cleanly.

---

### Feature 2: AI Resume Parsing

**Why**: Candidates often have skills not explicitly listed in their profile. Automated extraction enriches match scoring accuracy.

**Design decision**: Rule-based keyword matching (not LLM, not ML model). Simpler, fully offline, zero API cost, deterministic, fast.

**spaCy is installed but unused**: `en_core_web_sm` appears in `requirements.txt` and was an early experiment for NER-based extraction. It was superseded by the simpler keyword approach but left in for future use.

**FastAPI exposure**: `/parse-resume` makes the parser callable by any service over HTTP, without spinning up Django. Uses base64 encoding to keep the interface pure JSON.

**Interview questions**:
- "What are the limitations?" — No synonym resolution ("ML" ≠ "machine learning"), no context understanding, only detects from a fixed keyword list.
- "How would you improve it?" — LLM structured extraction (Claude/GPT), spaCy entity ruler with a custom skills vocab, or a fine-tuned BERT NER model.

---

### Feature 3: Match Scoring (70/30 Weighted Blend)

**Why**: Without objective ranking, HR must manually sort all applicants. A 0–100 score provides an immediate priority signal.

**Design decision**: 70% skill overlap + 30% TF-IDF cosine similarity. Skill overlap is higher-weighted because it's objective and directly tied to job requirements. TF-IDF catches qualitative fit (industry terms, domain context) that the keyword list misses.

**Why not pure TF-IDF?** A candidate who writes "Django" 10 times in their cover letter would outscore one who actually has the skill — skill overlap prevents gaming by frequency.

**Scoring is best-effort**: Wrapped in `try/except` everywhere. A scoring failure never blocks an application from being submitted.

**Interview questions**:
- "When is the score computed?" — At application submit time, stored in `ApplicationMatchScore`. Backfilled lazily for old applications when the applicant list is opened.
- "How would you improve accuracy?" — Pre-trained sentence transformers (BERT/MiniLM) for semantic similarity instead of TF-IDF; richer candidate text (all work experience, not just bio).

---

### Feature 4: Bias Criteria & Bias Agent

**Why**: Making implicit hiring preferences explicit creates accountability. HR is forced to justify their criteria, and the audit trail is visible.

**Design decision**: Dispatch table pattern (`_EVALUATORS` dict). Adding a new criterion type requires one function + one dict entry — no if/elif chain.

**The gender criterion controversy**: Legally prohibited in most jurisdictions. The platform's philosophy is "surface it, don't hide it" — by making it explicit and flagging it as `high` sensitivity, HR is made aware they're applying a potentially discriminatory filter. The system doesn't endorse it; it audits it.

**`api.py` approach**: Calls `_EVALUATORS[criterion](profile, value)` directly — skips `run_bias_agent()` which persists to DB. Uses `SimpleNamespace` to mock the ORM profile object.

**Interview questions**:
- "Isn't storing gender preference discriminatory?" — It models reality (some HR teams have implicit criteria). Making it explicit is the first step to challenging it.
- "How does college tier detection work?" — Keyword search in education text + parsed resume text against a hard-coded list of Indian institutions (Tier 1: IIT, IIM, BITS Pilani, etc.).

---

### Feature 5: FastAPI Microservice (`api.py`)

**Why**: Exposes AI utilities as language-agnostic JSON endpoints. A Node.js frontend or mobile app can call `/parse-resume` without embedding Python or Django.

**Design decision**: Single file, no Django, no DB. All four utilities are importable without Django being configured — verified by checking module-level imports (only `os`, `re`, `__future__`).

**`SimpleNamespace` mock**: The cleanest way to satisfy duck-typed ORM object access without creating real ORM instances. All attribute accesses in the evaluators are inside `try/except` blocks, making `SimpleNamespace` a safe mock.

**Interview questions**:
- "Why not Django REST Framework?" — DRF requires Django to be configured. The FastAPI service is designed to run independently, without a database.
- "How do you handle file uploads?" — JSON with base64 encoding (not multipart). This keeps the API interface uniform (pure JSON in, pure JSON out) at the cost of ~33% payload size increase from base64 overhead.

---

### Feature 6: Blind Review Mode

**Why**: Research shows blind review reduces hiring bias. HR can toggle it to focus on match score and skills alone.

**Design decision**: URL parameter (`?blind=1`) rather than a persisted setting — zero state, zero DB writes, instantly reversible.

**Limitation**: Hides data in the UI only. The data exists in the database. True blind review requires anonymisation at the data layer.

---

### Feature 7: HR Analytics Dashboard

**Why**: HR needs to understand their hiring funnel — where candidates drop off, what the average match score is, what the hire rate is.

**Design decision**: Django `annotate()` with conditional `Count()` — computes all funnel stages in a single query per job using `Q()` filters:

```python
jobs.annotate(
    apps_hired=Count('applications', filter=Q(applications__status='hired')),
    ...
)
```

**Interview questions**:
- "Would this scale?" — No. For large datasets, pre-aggregate into a denormalised analytics table updated by a Celery periodic task. The current approach recalculates on every page load.

---

## 13. Common Bugs & Debugging Guide

### Bug 1: `No module named 'fitz'` on resume parse
**Cause**: PyMuPDF not installed or venv not activated.
**Fix**: `pip install PyMuPDF` inside the venv. The import is lazy so the server starts fine but fails at parse time.

### Bug 2: Resume parsed but skills list is empty
**Cause**: Uploaded file is image-based PDF (scanned, not text-layer PDF). PyMuPDF's `get_text()` returns empty on scanned documents.
**Debug**: In Django shell: `from recruitment.utils.resume_parser import extract_text_from_resume; print(repr(extract_text_from_resume('/path/to/file.pdf'))[:200])`
**Fix**: For scanned PDFs, OCR is required (e.g. `pytesseract` + `pdf2image`) — not yet implemented.

### Bug 3: Match score shows 0 for all applicants
**Cause**: Either candidate has no skills and no parse result, or `score_text_similarity` returned 0.0 (empty candidate text).
**Debug**: `profile = user.candidate_profile; print(profile.skills, profile.parse_result.raw_text)`
**Note**: 0 is a valid score, not an error. The scoring is best-effort.

### Bug 4: Bias results not showing for new criteria
**Cause**: `ApplicationBiasResult` records are only created at application submit time OR when "Re-run Bias Check" is clicked. Old applications don't auto-update when new criteria are added.
**Fix**: Click "Re-run Bias Check" on the applicant list page (POST to `/hr/jobs/<pk>/bias-check/`).

### Bug 5: `UNIQUE constraint failed: recruitment_jobapplication`
**Cause**: Candidate applied twice (bypassed the view-level check somehow — e.g. double form submit).
**Note**: The `unique_together` constraint is the safety net. The view-level `.exists()` check normally catches this first.

### Bug 6: Notifications not appearing / count stuck at 0
**Debug steps**:
1. Check `settings.py` → `TEMPLATES → context_processors` includes `recruitment.context_processors.notifications_unread`
2. `Notification.objects.filter(user=request.user, unread=True).count()` in Django shell
3. Verify `Notification` records exist and have `unread=True`

### Bug 7: `python manage.py makemigrations` always shows "no changes" but migrate complains
**Cause**: Running from wrong directory or `recruitment` not in `INSTALLED_APPS`.
**Fix**: Ensure you're in the project root (where `manage.py` lives) and `INSTALLED_APPS` includes `'recruitment'`.

### Bug 8: `api.py /parse-resume` returns `{"skills": [], "experience_years": null, "education": ""}`
**Cause**: The base64 decoded correctly but the PDF has no extractable text (scanned). Or the wrong extension was provided in `filename` (e.g. `.txt` which is unsupported → empty string returned).
**Fix**: Verify `filename` has `.pdf` or `.docx` extension. Check `raw_text` in the response — if it's empty, the extraction failed silently.

### Bug 9: `manage.py makemigrations` generated migration 0006 unexpectedly
**Cause**: Django 5 changed `DEFAULT_AUTO_FIELD` to `BigAutoField`. The existing models relied on the implicit default. Migration 0006 explicitly sets `AutoField` on all PKs to silence the detector.
**This is expected behaviour** — apply the migration and move on.

### Common Developer Mistakes
1. Running `manage.py makemigrations` without the `python` prefix
2. Not activating venv before running any command
3. Editing `db.sqlite3` directly — use Django shell or admin
4. Forgetting to restart dev server after `.env` changes — python-decouple reads at startup
5. Adding a view to `views.py` but forgetting to register a URL in `urls.py`
6. Calling `run_bias_agent()` from `api.py` — it will try to import Django models and fail

---

## 14. Future Improvements

### Scalability

1. **SQLite → PostgreSQL**: SQLite has a single writer. Any real concurrent load requires PostgreSQL.
2. **Celery + Redis for async tasks**: Resume parsing, match scoring, email sending all happen synchronously in the request cycle. Offload to Celery workers.
3. **Pre-computed analytics**: HR analytics recalculates on every request. Pre-aggregate into a `HiringAnalyticsSummary` table via Celery periodic task.
4. **Media files → S3**: Serving resumes through Django is slow. Move `media/` to S3 or equivalent.
5. **Redis caching for notification count**: Currently queries DB on every page load via context processor. Cache with a 5-second TTL.

### Performance

1. **Skill deduplication in DB not Python**: The skill merge loop in `applicant_list` view is O(n×m) in Python. Move to a DB-level aggregation.
2. **TF-IDF per-request is expensive**: For the job list page (scoring candidate against many jobs), re-fitting the vectoriser per job is wasteful. Cache TF-IDF candidate embeddings.
3. **`select_related` audit**: Verify with Django Debug Toolbar that no N+1 queries are occurring on applicant list.

### Security

1. **Rate limiting on login**: Add `django-axes` or `django-ratelimit`.
2. **File type validation**: Validate uploaded resumes by MIME type, not just extension.
3. **HTTPS enforcement**: `SECURE_SSL_REDIRECT = True`, `HSTS_SECONDS = 31536000` in production.
4. **`api.py` authentication**: Add Bearer token middleware or put behind API gateway.
5. **Audit log**: Log all status changes, bias criteria modifications, admin actions.
6. **Content Security Policy headers**.

### Feature Ideas

1. **LLM-powered resume parsing**: Replace keyword matching with Claude/GPT structured extraction — much higher accuracy, handles synonyms and context.
2. **Automated candidate ranking**: Sort applicant list by match score by default.
3. **Google Calendar / Outlook OAuth**: Real-time slot availability instead of manual datetime pickers.
4. **Candidate-facing score explanation**: Show breakdown (which skills matched, which didn't).
5. **Bulk status update**: Select multiple applicants → change status in batch.
6. **Job template library**: Save and reuse job posting templates.
7. **Multi-tenant / SaaS mode**: Company-level data isolation.
8. **Diversity dashboard**: Show HR the demographic breakdown of applicant pool and hired candidates over time.
9. **spaCy NLP**: `en_core_web_sm` is already installed — use it for organisation name extraction, location normalisation, job title NER from resumes.
10. **WebSocket notifications**: Replace the polling-on-dashboard-load pattern with real-time push notifications.

---

## 15. Project Explanation Scripts

### 30-Second Explanation

> "FairHire is a Django recruitment platform with an optional FastAPI microservice. HR teams post jobs with configurable hiring criteria; when candidates apply, the system automatically parses their PDF resume using PyMuPDF, computes a 0–100 fit score using TF-IDF cosine similarity and skill overlap, and evaluates them against the HR's criteria. There's also a bias detector that flags gendered or ageist language in job descriptions before they're published. The FastAPI service exposes all four AI modules as pure JSON REST endpoints — no Django required."

---

### 2-Minute Explanation

> "FairHire is a full-stack recruitment platform with two server components: a Django 5 app serving the website, and a FastAPI microservice wrapping the AI utilities as REST endpoints.
>
> The Django app serves two roles: HR recruiters and job candidates. HR can post jobs — and when they do, a bias detector scans the description for masculine-coded words like 'ninja' or 'rockstar' and ageist terms like 'digital native' before it's published. HR can also define structured hiring criteria per job: minimum experience, college tier, gender preference, or custom keyword rules.
>
> When a candidate applies, three things happen automatically in the background: first, the system computes a 0–100 fit score — 70% from skill keyword overlap between the candidate's skills and the job requirements, and 30% from TF-IDF cosine similarity between the resume text and the job description. Second, the bias agent evaluates the candidate against every HR criterion and stores a pass/fail result with an explanation. Third, notifications are sent to both parties.
>
> Candidates can also trigger AI resume parsing — they upload a PDF or DOCX, the system extracts text with PyMuPDF, detects 100+ skill keywords, infers years of experience with regex, and merges the findings back into their profile.
>
> The platform also handles interview scheduling (HR proposes time slots, candidate picks one), in-app messaging, and calendar export as `.ics` files. HR gets an analytics dashboard with per-job funnel metrics.
>
> The FastAPI service (`api.py`) exposes the four AI utilities — `/parse-resume`, `/score-match`, `/evaluate-bias`, `/detect-bias` — as pure JSON endpoints that any service can call without touching Django or the database."

---

### 5-Minute Explanation

> "Let me walk you through FairHire end to end — architecture, AI pipeline, and the design decisions I'd defend in any interview.
>
> **The two-server architecture.** FairHire runs two services. The main Django 5 app on port 8000 handles the full website — authentication, job board, HR dashboard, candidate dashboard, interviews, messaging, analytics. The FastAPI microservice on port 8001 is a thin JSON wrapper around the four AI utility modules, designed so any service can call them without spinning up Django. The crucial design decision: all four utility modules — `resume_parser.py`, `match_scorer.py`, `bias_agent.py`, `bias_detector.py` — were written with zero Django dependencies at module load time. Heavy imports like PyMuPDF and scikit-learn are lazy (inside function bodies). This is what makes the FastAPI service possible.
>
> **The data model.** There are 11 database models in a single Django app. The core chain is: `CustomUser` → `CandidateProfile` → `ResumeParseResult`. And: `CustomUser` (HR) → `JobPosting` → `JobApplication` → `ApplicationMatchScore` + `ApplicationBiasResult`. Communication is handled through `Notification`, `Message`, and `InterviewSlot` models, all anchored to `JobApplication`.
>
> **The AI pipeline.** When a candidate applies, four things happen in sequence — all best-effort, all wrapped in `try/except` so a failure never blocks the application:
> One: resume text is retrieved (from profile or parsed result), and match scoring runs. The composite score is `skill_overlap × 0.70 + TF-IDF_cosine × 0.30`. Skill overlap is a simple set intersection: how many of the required skills appear in the candidate's skill set. TF-IDF cosine similarity is computed with scikit-learn between the candidate's resume text and the full job description. The 70/30 weighting favours the objective signal.
> Two: the bias agent evaluates the candidate against every `JobBiasCriteria` defined for that job. The agent uses a dispatch table — `{'experience_min': evaluate_experience, 'college_tier': evaluate_college_tier, ...}` — so adding a new criterion type is a one-line change. The college tier evaluator does keyword search against a curated list of Indian institutions.
> Three and four: notifications and emails.
>
> **Resume parsing.** The candidate uploads a PDF. On demand, PyMuPDF extracts plain text, a 100+ keyword list detects skills with whole-word regex, a regex pattern extracts the maximum years of experience, and another pattern finds the first degree-containing line. Parsed skills are merged into the candidate's manual profile (union, case-insensitive), so both data sources enrich future match scores.
>
> **Bias detection.** Before a job is published, `scan_job_description()` runs — four lexicon categories (gendered masculine, gendered feminine, ageist, ableist) matched with word-boundary regex. HR sees warnings but can still publish — advisory, not blocking.
>
> **The FastAPI microservice.** `api.py` imports only `_EVALUATORS` from `bias_agent` — not `run_bias_agent()`, which would trigger a Django ORM import. The bias evaluators expect duck-typed profile objects; `SimpleNamespace` satisfies every attribute access since the evaluators already wrap `parse_result` access in `try/except`. `/parse-resume` accepts base64-encoded file bytes in JSON (not multipart), writes a temp file with the correct extension, calls the parser, then deletes the temp file unconditionally in a `finally` block.
>
> **What I'd improve with more time:** PostgreSQL instead of SQLite; Celery for async AI processing; LLM-based resume parsing for semantic understanding; pre-aggregated analytics; Bearer token auth on the FastAPI service; and a WebSocket-based notification system instead of the current poll-on-dashboard-load approach."

---

*Document generated: July 2026 | Covers: Django app (migrations 0001–0006) + FastAPI microservice (api.py v1.0)*

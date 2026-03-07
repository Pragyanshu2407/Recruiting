# FairHire Project Documentation

## Phase 1: Foundation & User Management

### 1. Initial Project Scaffolding

**Objective:** Initialize the Django project and set up the basic environment.

**Implementation Details:**

1.  **Virtual Environment:**
    *   Created a virtual environment using `python3 -m venv venv`.
    *   Activated using `source venv/bin/activate`.
    *   Installed Django: `pip install django`.

2.  **Project Initialization:**
    *   Created Django project: `django-admin startproject FairHire .`.
    *   Created App: `python manage.py startapp recruitment`.

3.  **Settings Configuration (`FairHire/settings.py`):**
    *   **Installed Apps:** Added `recruitment` to `INSTALLED_APPS`.
    *   **Static Files:**
        *   `STATIC_URL = "static/"`
        *   `STATIC_ROOT = BASE_DIR / "staticfiles"` (For collecting static files in production)
        *   `STATICFILES_DIRS = [BASE_DIR / "static"]` (For development static files)
    *   **Media Files:**
        *   `MEDIA_URL = "/media/"`
        *   `MEDIA_ROOT = BASE_DIR / "media"` (For storing user-uploaded files like resumes)

**Directory Structure:**

```
FairHire/
├── FairHire/
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── recruitment/
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   └── ...
├── static/ (Created for global static files)
├── media/ (Created for uploaded media files)
├── manage.py
└── venv/
```

### 2. Multi-User Authentication

**Objective:** Implement custom user types (HR and Candidate) and authentication flows.

**Implementation Details:**

1.  **Custom User Model (`recruitment/models.py`):**
    *   `CustomUser` inherits from `AbstractUser` with:
        *   `is_hr` and `is_candidate` flags
        *   unique `email`
    *   Profiles:
        *   `HRProfile` (company info, logo, website, description)
        *   `CandidateProfile` (bio, skills, experience_years, education, resume, links, gender)
    *   Updated `AUTH_USER_MODEL` in `settings.py` → `'recruitment.CustomUser'`.

2.  **Forms (`recruitment/forms.py`):**
    *   `HRSignUpForm`: Inherits `UserCreationForm`. Sets `is_hr=True` on save.
    *   `CandidateSignUpForm`: Inherits `UserCreationForm`. Sets `is_candidate=True` on save.

3.  **Views (`recruitment/views.py`):**
    *   **Sign Up:**
        *   `HRSignUpView`: Uses `HRSignUpForm`, redirects to `hr_dashboard`.
        *   `CandidateSignUpView`: Uses `CandidateSignUpForm`, redirects to `candidate_dashboard`.
    *   **Login:**
        *   `CustomLoginView`: Inherits `LoginView`. Redirects using URL names:
            *   HR → `reverse('hr_dashboard')`
            *   Candidate → `reverse('candidate_dashboard')`
    *   **Dashboards:**
        *   `hr_dashboard`: Restricted to HR users.
        *   `candidate_dashboard`: Restricted to Candidate users.
    *   **Home:** Simple landing page.

4.  **URLs (`recruitment/urls.py`):**
    *   General: `login/`, `logout/`, `signup/hr/`, `signup/candidate/`
    *   HR: `hr/dashboard/`, `hr/profile/`, `hr/jobs/new|edit|delete|applicants|bias-check`, `hr/applications/<id>/status/`
    *   Candidate: `candidate/dashboard/`, `candidate/profile/`, `candidate/applications/`, `candidate/parse-resume/`
    *   Public: `jobs/`, `jobs/<id>/`, `jobs/<id>/apply/`

5.  **Templates (`recruitment/templates/`):**
    *   `base.html`: Main layout with navigation that adapts to login state.
    *   `recruitment/home.html`: Landing page.
    *   `registration/signup_form.html`: Generic sign-up template used by both views.
    *   `registration/login.html`: Login form.
    *   `recruitment/hr_dashboard.html`: HR specific dashboard.
    *   `recruitment/candidate_dashboard.html`: Candidate specific dashboard.

---

## Phase 2: Core Recruitment Features

**Models (`recruitment/models.py`):**
- `JobPosting`: title, description, required_skills (CSV), location, location_type, salary range, deadline, status; helpers `required_skills_list()`, `application_count()`.
- `JobApplication`: FK job + candidate, cover_letter, optional resume_snapshot, status, hr_notes; unique `(job, candidate)`; `STATUS_COLORS`.

**Candidate Tools:**
- `candidate_dashboard`, `candidate_profile_edit`, `my_applications`
- Job board: `job_list`, `job_detail`, `job_apply`

**HR Tools:**
- `hr_dashboard`, `hr_profile_edit`
- Job CRUD: `job_create`, `job_edit`, `job_delete`
- Applicants & status: `applicant_list`, `application_update_status`

**Templates:** job list/detail/apply, applicant list, status form, job form, profiles.

UI Enhancement:
- Job form now includes role-based Skill Presets (Frontend, Backend, ML, Data Engineering, DevOps, Mobile, Full Stack). Selecting a preset renders checkboxes you can add into the “Required Skills” field. Selected skills are merged and deduplicated as comma‑separated values.

---

## Phase 3: AI & Fair Hiring Core

**Resume Parsing (`recruitment/utils/resume_parser.py`):**
- Extracts text from PDF/DOCX (PyMuPDF, python-docx).
- Parses skills via dictionary matching, years of experience via regex, and education lines.
- Stored in `ResumeParseResult`; merged back into `CandidateProfile` on parse.

**AI Job Matching (`recruitment/utils/match_scorer.py`):**
- Skill overlap (70%) + TF‑IDF cosine similarity (30%, scikit‑learn).
- Stored in `ApplicationMatchScore`; also displayed in lists.

**Custom Bias Agent (`recruitment/utils/bias_agent.py`):**
- HR defines `JobBiasCriteria` per job (experience_min, college_tier, gender, custom).
- `run_bias_agent(application)` evaluates and stores `ApplicationBiasResult`.
- Bulk re-check available via `run_bias_check_view`.

Value formats:
- Experience: supports `5`, `3+`, or ranges like `2-4` (inclusive).
- College Tier: `Tier 1`/`Tier 2` (IISc is matched precisely, not generic `isc`).
- Gender: e.g., `Female`, `Male`, `Non-binary`, or `Any`.
- Custom: any keyword/phrase searched across profile + parsed resume text.
**Bias Detection in Job Descriptions (`recruitment/utils/bias_detector.py`):**
- Flags gendered/ageist/ableist terms on job create/edit with actionable suggestions.

**URLs/Views:** See Phase 2; Phase 3 hooks are integrated in create/edit/apply flows.

**Dependencies:** Ensure the venv has:
- `scikit-learn`, `python-docx`, `PyMuPDF`

**Notes:**
- All AI features fail gracefully if dependencies or data are missing — they never block user flows.

---

## Phase 4: Communication & Workflow

**Email Notifications**
- Console backend configured for development; emails print to server logs.
- Triggers:
  - On application submission (HR notified; candidate ack)
  - On application status change (candidate notified)

**In‑App Notifications**
- Model: Notification (user, title, body, link, unread, created_at)
- List view at /notifications/ and badges shown in dashboards via context.

**Interview Scheduler**
- HR can propose up to 3 time slots per application:
  - /hr/applications/<id>/interview/propose/
- Candidate chooses a slot:
  - /candidate/applications/<id>/interview/
- Booking marks the chosen slot as booked and cancels the rest; both parties are notified (in‑app + email).
- Model: InterviewSlot (application, start_time, end_time, status, proposed_by, booked_by)

**Messaging (basic)**
- Model: Message (application, sender, text, created_at)
- Thread at /messages/<application_id>/ with simple send form

---

## Phase 5: Calendar Integration & Reminders

**Calendar**
- .ics download endpoint for interview slots: `/slots/<slot_id>/ics/` (secure for HR owner and candidate).
- Quick-add buttons:
  - Google Calendar link prefilled with start/end/summary.
  - Outlook web compose link with start/end/subject.
- Shown on both HR and Candidate dashboards in “Upcoming Interviews”.

**Reminders**
- 24‑hour reminders for booked interviews:
  - On dashboard load, creates a one-time in‑app notification if an interview starts in the next 24h (idempotent by title+link).
- Header bell shows unread notifications count via a context processor.

**Files**
- Views: calendar ICS and reminder logic in `recruitment/views.py`
- Context processor: `recruitment/context_processors.py` (+ settings template config)
- Templates updated: HR and Candidate dashboards, base header bell badge.

---

## Phase 6: Reporting & Export

**Objectives**
- Give HR a consolidated view of the hiring funnel per job.
- Enable one-click CSV export of applicants for offline analysis.

**Features**
- HR Analytics page at `/hr/analytics/`:
  - Per‑job metrics: total, applied, shortlisted, interview, hired, rejected, withdrawn.
  - Conversion rates: shortlist rate, hire rate.
  - Average fit score per job (from `ApplicationMatchScore`).
- CSV Export on Applicants page:
  - Button “Export CSV” downloads `applicants_job_<job_id>.csv`.
  - Columns: Candidate Name, Email, Status, Applied At, Match Score, Experience Years, Skills (merged profile+parsed, deduped), Bias Passed, Bias Failed.

**URLs/Views**
- `/hr/analytics/` → `hr_analytics`
- `/hr/jobs/<id>/export.csv` → `export_applicants_csv`

**Templates**
- `recruitment/templates/recruitment/hr_analytics.html`
- Applicant list header now shows “Export CSV” and “Analytics” shortcuts.

**Notes**
- Aggregations use `annotate` with conditional `Count` filters; average scores via a single aggregate pass over `ApplicationMatchScore`.
- Exports are restricted to the job’s owning HR via `hr_required` and owner checks.

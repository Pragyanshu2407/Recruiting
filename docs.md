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
    *   Created `CustomUser` inheriting from `AbstractUser`.
    *   Added fields:
        *   `is_hr`: BooleanField (default=False)
        *   `is_candidate`: BooleanField (default=False)
    *   Updated `AUTH_USER_MODEL` in `settings.py` to `'recruitment.CustomUser'`.

2.  **Forms (`recruitment/forms.py`):**
    *   `HRSignUpForm`: Inherits `UserCreationForm`. Sets `is_hr=True` on save.
    *   `CandidateSignUpForm`: Inherits `UserCreationForm`. Sets `is_candidate=True` on save.

3.  **Views (`recruitment/views.py`):**
    *   **Sign Up:**
        *   `HRSignUpView`: Uses `HRSignUpForm`, redirects to `hr_dashboard`.
        *   `CandidateSignUpView`: Uses `CandidateSignUpForm`, redirects to `candidate_dashboard`.
    *   **Login:**
        *   `CustomLoginView`: Inherits `LoginView`.
        *   Overrides `get_success_url` to redirect HRs to `/hr_dashboard/` and Candidates to `/candidate_dashboard/`.
    *   **Dashboards:**
        *   `hr_dashboard`: Restricted to HR users.
        *   `candidate_dashboard`: Restricted to Candidate users.
    *   **Home:** Simple landing page.

4.  **URLs (`recruitment/urls.py`):**
    *   `signup/hr/` -> `HRSignUpView`
    *   `signup/candidate/` -> `CandidateSignUpView`
    *   `login/` -> `CustomLoginView`
    *   `logout/` -> `LogoutView`
    *   `hr_dashboard/` -> `hr_dashboard`
    *   `candidate_dashboard/` -> `candidate_dashboard`

5.  **Templates (`recruitment/templates/`):**
    *   `base.html`: Main layout with navigation that adapts to login state.
    *   `recruitment/home.html`: Landing page.
    *   `registration/signup_form.html`: Generic sign-up template used by both views.
    *   `registration/login.html`: Login form.
    *   `recruitment/hr_dashboard.html`: HR specific dashboard.
    *   `recruitment/candidate_dashboard.html`: Candidate specific dashboard.

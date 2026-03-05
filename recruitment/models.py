from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    is_hr = models.BooleanField(default=False)
    is_candidate = models.BooleanField(default=False)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class HRProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hr_profile'
    )
    company_name = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    company_website = models.URLField(blank=True)
    company_description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} — {self.company_name}"


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidate_profile'
    )
    bio = models.TextField(blank=True)
    skills = models.TextField(
        blank=True, help_text="Comma-separated list of skills, e.g. Python, Django, SQL"
    )
    experience_years = models.PositiveIntegerField(default=0)
    education = models.CharField(max_length=300, blank=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    def skills_list(self):
        """Returns skills as a Python list."""
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    def __str__(self):
        return f"{self.user.username}'s Profile"


class JobPosting(models.Model):
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_DRAFT = 'draft'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_DRAFT, 'Draft'),
    ]

    LOCATION_REMOTE = 'remote'
    LOCATION_ONSITE = 'onsite'
    LOCATION_HYBRID = 'hybrid'
    LOCATION_CHOICES = [
        (LOCATION_REMOTE, 'Remote'),
        (LOCATION_ONSITE, 'On-site'),
        (LOCATION_HYBRID, 'Hybrid'),
    ]

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='job_postings'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_skills = models.TextField(
        help_text="Comma-separated list of required skills, e.g. Python, Django, SQL"
    )
    location = models.CharField(max_length=200, blank=True)
    location_type = models.CharField(
        max_length=10, choices=LOCATION_CHOICES, default=LOCATION_ONSITE
    )
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def required_skills_list(self):
        return [s.strip() for s in self.required_skills.split(',') if s.strip()]

    def application_count(self):
        return self.applications.count()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} @ {self.posted_by.hr_profile.company_name if hasattr(self.posted_by, 'hr_profile') else self.posted_by.username}"


class JobApplication(models.Model):
    STATUS_APPLIED = 'applied'
    STATUS_SHORTLISTED = 'shortlisted'
    STATUS_INTERVIEW = 'interview'
    STATUS_HIRED = 'hired'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'

    STATUS_CHOICES = [
        (STATUS_APPLIED, 'Applied'),
        (STATUS_SHORTLISTED, 'Shortlisted'),
        (STATUS_INTERVIEW, 'Interview Scheduled'),
        (STATUS_HIRED, 'Hired'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_WITHDRAWN, 'Withdrawn'),
    ]

    STATUS_COLORS = {
        STATUS_APPLIED: '#3b82f6',
        STATUS_SHORTLISTED: '#f59e0b',
        STATUS_INTERVIEW: '#8b5cf6',
        STATUS_HIRED: '#10b981',
        STATUS_REJECTED: '#ef4444',
        STATUS_WITHDRAWN: '#6b7280',
    }

    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name='applications'
    )
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications'
    )
    cover_letter = models.TextField(blank=True)
    resume_snapshot = models.FileField(
        upload_to='application_resumes/', blank=True, null=True,
        help_text="Upload a resume specific to this application (optional, uses profile resume otherwise)"
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_APPLIED
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    hr_notes = models.TextField(blank=True, help_text="Internal HR notes (not visible to candidate)")

    class Meta:
        unique_together = ('job', 'candidate')
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.candidate.username} → {self.job.title}"


# ── Phase 3: Resume Parsing & Match Scoring ───────────────────────────────────

class ResumeParseResult(models.Model):
    """Stores structured data extracted from a candidate's uploaded resume."""
    candidate = models.OneToOneField(
        CandidateProfile, on_delete=models.CASCADE, related_name='parse_result'
    )
    raw_text = models.TextField(blank=True)
    parsed_skills = models.TextField(
        blank=True, help_text="Comma-separated skills extracted from the resume"
    )
    parsed_experience_years = models.PositiveIntegerField(null=True, blank=True)
    parsed_education = models.CharField(max_length=400, blank=True)
    parsed_at = models.DateTimeField(auto_now=True)

    def parsed_skills_list(self) -> list:
        """Return parsed skills as a Python list."""
        return [s.strip() for s in self.parsed_skills.split(',') if s.strip()]

    def __str__(self):
        return f"ParseResult for {self.candidate}"


class ApplicationMatchScore(models.Model):
    """Stores the computed fit score for a job application."""
    application = models.OneToOneField(
        JobApplication, on_delete=models.CASCADE, related_name='match_score'
    )
    score = models.PositiveSmallIntegerField(default=0)          # 0-100
    skill_overlap_pct = models.FloatField(default=0.0)
    text_similarity_pct = models.FloatField(default=0.0)
    computed_at = models.DateTimeField(auto_now=True)

    def score_label(self) -> str:
        """Return a human-readable strength label."""
        if self.score >= 70:
            return "Strong"
        elif self.score >= 40:
            return "Moderate"
        return "Weak"

    def score_color(self) -> str:
        """Return a CSS colour string corresponding to the score level."""
        if self.score >= 70:
            return "#10b981"   # green
        elif self.score >= 40:
            return "#f59e0b"   # amber
        return "#ef4444"       # red

    def __str__(self):
        return f"{self.application} — {self.score}%"

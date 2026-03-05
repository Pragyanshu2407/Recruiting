from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView
from django.db.models import Q

from .forms import (
    HRSignUpForm, CandidateSignUpForm,
    HRProfileForm, CandidateProfileForm,
    JobPostingForm, JobApplicationForm,
    ApplicationStatusForm, JobSearchForm,
)
from .models import (
    CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication,
    ResumeParseResult, ApplicationMatchScore,
)
from .utils.resume_parser import parse_resume
from .utils.match_scorer import compute_match_score, score_skills_overlap


# ── Helpers / Mixins ─────────────────────────────────────────────────────────

def hr_required(view_func):
    """Decorator that checks the user is an authenticated HR user."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_hr:
            messages.error(request, "Access denied. HR accounts only.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


def candidate_required(view_func):
    """Decorator that checks the user is an authenticated Candidate."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_candidate:
            messages.error(request, "Access denied. Candidate accounts only.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Auth Views ───────────────────────────────────────────────────────────────

class HRSignUpView(CreateView):
    model = CustomUser
    form_class = HRSignUpForm
    template_name = 'registration/signup_form.html'

    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'HR'
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome to FairHire, {user.username}! Complete your company profile below.")
        return redirect('hr_dashboard')


class CandidateSignUpView(CreateView):
    model = CustomUser
    form_class = CandidateSignUpForm
    template_name = 'registration/signup_form.html'

    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'Candidate'
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome to FairHire, {user.username}! Complete your profile to get started.")
        return redirect('candidate_dashboard')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        user = self.request.user
        if user.is_hr:
            return '/hr_dashboard/'
        elif user.is_candidate:
            return '/candidate_dashboard/'
        return '/'


# ── General Views ────────────────────────────────────────────────────────────

def home(request):
    open_jobs_count = JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).count()
    return render(request, 'recruitment/home.html', {'open_jobs_count': open_jobs_count})


# ── HR Dashboard & Profile ───────────────────────────────────────────────────

@hr_required
def hr_dashboard(request):
    job_postings = JobPosting.objects.filter(posted_by=request.user)
    total_applications = JobApplication.objects.filter(job__posted_by=request.user).count()
    open_jobs = job_postings.filter(status=JobPosting.STATUS_OPEN).count()
    shortlisted = JobApplication.objects.filter(
        job__posted_by=request.user, status=JobApplication.STATUS_SHORTLISTED
    ).count()

    context = {
        'job_postings': job_postings,
        'total_applications': total_applications,
        'open_jobs': open_jobs,
        'shortlisted': shortlisted,
    }
    return render(request, 'recruitment/hr_dashboard.html', context)


@hr_required
def hr_profile_edit(request):
    profile, _ = HRProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = HRProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('hr_dashboard')
    else:
        form = HRProfileForm(instance=profile, user=request.user)
    return render(request, 'recruitment/hr_profile.html', {'form': form})


# ── Job Posting CRUD (HR) ────────────────────────────────────────────────────

@hr_required
def job_create(request):
    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.save()
            messages.success(request, f"Job '{job.title}' posted successfully!")
            return redirect('hr_dashboard')
    else:
        form = JobPostingForm()
    return render(request, 'recruitment/job_form.html', {'form': form, 'action': 'Create'})


@hr_required
def job_edit(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    if request.method == 'POST':
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated successfully!")
            return redirect('hr_dashboard')
    else:
        form = JobPostingForm(instance=job)
    return render(request, 'recruitment/job_form.html', {'form': form, 'action': 'Edit', 'job': job})


@hr_required
def job_delete(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    if request.method == 'POST':
        job.delete()
        messages.success(request, "Job posting deleted.")
        return redirect('hr_dashboard')
    return render(request, 'recruitment/job_confirm_delete.html', {'job': job})


@hr_required
def applicant_list(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    applications = job.applications.select_related(
        'candidate', 'candidate__candidate_profile'
    ).prefetch_related('match_score').all()
    return render(request, 'recruitment/applicant_list.html', {'job': job, 'applications': applications})


@hr_required
def application_update_status(request, pk):
    application = get_object_or_404(JobApplication, pk=pk, job__posted_by=request.user)
    if request.method == 'POST':
        form = ApplicationStatusForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"Status updated to '{application.get_status_display()}'.")
            return redirect('applicant_list', pk=application.job.pk)
    else:
        form = ApplicationStatusForm(instance=application)
    return render(request, 'recruitment/application_status_form.html', {
        'form': form, 'application': application
    })


# ── Job Board & Applications (Candidate) ─────────────────────────────────────

def job_list(request):
    """Public job board — accessible to anyone."""
    form = JobSearchForm(request.GET or None)
    jobs = JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).select_related(
        'posted_by', 'posted_by__hr_profile'
    )

    if form.is_valid():
        q = form.cleaned_data.get('q')
        location_type = form.cleaned_data.get('location_type')
        skills = form.cleaned_data.get('skills')

        if q:
            jobs = jobs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(required_skills__icontains=q))
        if location_type:
            jobs = jobs.filter(location_type=location_type)
        if skills:
            for skill in skills.split(','):
                skill = skill.strip()
                if skill:
                    jobs = jobs.filter(required_skills__icontains=skill)

    # Phase 3: For logged-in candidates, compute a rough match % per job
    match_scores = {}
    if request.user.is_authenticated and request.user.is_candidate:
        try:
            from .utils.match_scorer import score_skills_overlap, score_text_similarity
            candidate_skills = []
            candidate_text = ""
            try:
                profile = request.user.candidate_profile
                candidate_skills.extend(profile.skills_list())
                candidate_text = profile.bio + " " + profile.skills + " " + profile.education
            except Exception:
                pass
            try:
                pr = request.user.candidate_profile.parse_result
                candidate_skills.extend(pr.parsed_skills_list())
                if pr.raw_text:
                    candidate_text = pr.raw_text
            except Exception:
                pass

            if candidate_skills or candidate_text.strip():
                for job in jobs:
                    skill_pct = score_skills_overlap(candidate_skills, job.required_skills_list())
                    job_text = f"{job.title} {job.description} {job.required_skills}"
                    text_pct = score_text_similarity(candidate_text, job_text)
                    match_scores[job.pk] = min(100, max(0, round(skill_pct * 0.70 + text_pct * 0.30)))
        except Exception:
            pass

    return render(request, 'recruitment/job_list.html', {'jobs': jobs, 'form': form, 'match_scores': match_scores})


def job_detail(request, pk):
    """Job detail — public view. Shows apply button if logged in as candidate."""
    job = get_object_or_404(JobPosting, pk=pk)
    already_applied = False
    if request.user.is_authenticated and request.user.is_candidate:
        already_applied = JobApplication.objects.filter(job=job, candidate=request.user).exists()
    return render(request, 'recruitment/job_detail.html', {
        'job': job, 'already_applied': already_applied
    })


@candidate_required
def job_apply(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, status=JobPosting.STATUS_OPEN)

    if JobApplication.objects.filter(job=job, candidate=request.user).exists():
        messages.warning(request, "You have already applied to this job.")
        return redirect('job_detail', pk=pk)

    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.candidate = request.user
            application.save()

            # ── Phase 3: compute & store match score on apply ────────────
            try:
                from .utils.match_scorer import score_text_similarity
                required = job.required_skills_list()
                candidate_skills = []
                try:
                    candidate_skills.extend(request.user.candidate_profile.skills_list())
                except Exception:
                    pass
                try:
                    candidate_skills.extend(
                        request.user.candidate_profile.parse_result.parsed_skills_list()
                    )
                except Exception:
                    pass

                candidate_text = ""
                try:
                    candidate_text = request.user.candidate_profile.parse_result.raw_text or ""
                except Exception:
                    pass
                if not candidate_text:
                    try:
                        p = request.user.candidate_profile
                        candidate_text = " ".join(filter(None, [p.bio, p.skills, p.education]))
                    except Exception:
                        pass

                job_text = f"{job.title} {job.description} {job.required_skills}"
                skill_pct = score_skills_overlap(candidate_skills, required)
                text_pct = score_text_similarity(candidate_text, job_text)
                composite = min(100, max(0, round(skill_pct * 0.70 + text_pct * 0.30)))

                ApplicationMatchScore.objects.update_or_create(
                    application=application,
                    defaults={
                        'score': composite,
                        'skill_overlap_pct': skill_pct,
                        'text_similarity_pct': text_pct,
                    }
                )
            except Exception:
                pass  # Scoring is best-effort; never block an application
            # ────────────────────────────────────────────────────────────

            messages.success(request, f"Applied to '{job.title}' successfully! Good luck!")
            return redirect('my_applications')
    else:
        form = JobApplicationForm()
    return render(request, 'recruitment/job_apply.html', {'form': form, 'job': job})


# ── Candidate Dashboard & Profile ────────────────────────────────────────────

@candidate_required
def candidate_dashboard(request):
    applications = JobApplication.objects.filter(
        candidate=request.user
    ).select_related('job', 'job__posted_by', 'job__posted_by__hr_profile').prefetch_related('match_score')

    status_counts = {}
    for choice_val, _ in JobApplication.STATUS_CHOICES:
        status_counts[choice_val] = applications.filter(status=choice_val).count()

    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    profile_complete = bool(profile.skills and profile.education)

    # Phase 3: resume parse result (None if not yet parsed)
    parse_result = getattr(profile, 'parse_result', None)

    context = {
        'applications': applications,
        'status_counts': status_counts,
        'profile': profile,
        'profile_complete': profile_complete,
        'open_jobs_count': JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).count(),
        'parse_result': parse_result,
    }
    return render(request, 'recruitment/candidate_dashboard.html', context)


@candidate_required
def candidate_profile_edit(request):
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = CandidateProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('candidate_dashboard')
    else:
        form = CandidateProfileForm(instance=profile, user=request.user)
    return render(request, 'recruitment/candidate_profile.html', {'form': form, 'profile': profile})


@candidate_required
def my_applications(request):
    applications = JobApplication.objects.filter(
        candidate=request.user
    ).select_related('job', 'job__posted_by', 'job__posted_by__hr_profile').prefetch_related('match_score')
    return render(request, 'recruitment/my_applications.html', {'applications': applications})


# ── Phase 3: Resume Parsing ───────────────────────────────────────────────────

@candidate_required
def parse_resume_view(request):
    """POST-only view that triggers resume parsing for the logged-in candidate."""
    if request.method != 'POST':
        return redirect('candidate_dashboard')

    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

    if not profile.resume:
        messages.warning(request, "Please upload your resume first via Edit Profile.")
        return redirect('candidate_profile')

    try:
        result = parse_resume(profile.resume.path)

        skills_str = ', '.join(result['skills'])
        ResumeParseResult.objects.update_or_create(
            candidate=profile,
            defaults={
                'raw_text': result['raw_text'],
                'parsed_skills': skills_str,
                'parsed_experience_years': result['experience_years'],
                'parsed_education': result['education'],
            }
        )

        # Merge parsed skills back into the profile's manual skills field (union)
        existing = set(s.strip().lower() for s in profile.skills.split(',') if s.strip())
        new_skills = [s for s in result['skills'] if s.lower() not in existing]
        if new_skills:
            merged = profile.skills + (', ' if profile.skills else '') + ', '.join(new_skills)
            profile.skills = merged

        # Backfill experience_years and education if not already set
        if result['experience_years'] and not profile.experience_years:
            profile.experience_years = result['experience_years']
        if result['education'] and not profile.education:
            profile.education = result['education']

        profile.save()

        skill_count = len(result['skills'])
        messages.success(
            request,
            f"Resume parsed successfully! Found {skill_count} skill{'s' if skill_count != 1 else ''}, "
            f"{result['experience_years'] or 0} years of experience."
        )
    except Exception as e:
        messages.error(request, f"Could not parse resume: {e}")

    return redirect('candidate_dashboard')

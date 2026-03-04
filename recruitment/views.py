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
from .models import CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication


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
    applications = job.applications.select_related('candidate', 'candidate__candidate_profile').all()
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

    return render(request, 'recruitment/job_list.html', {'jobs': jobs, 'form': form})


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
    ).select_related('job', 'job__posted_by', 'job__posted_by__hr_profile')

    status_counts = {}
    for choice_val, _ in JobApplication.STATUS_CHOICES:
        status_counts[choice_val] = applications.filter(status=choice_val).count()

    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    profile_complete = bool(profile.skills and profile.education)

    context = {
        'applications': applications,
        'status_counts': status_counts,
        'profile': profile,
        'profile_complete': profile_complete,
        'open_jobs_count': JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).count(),
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
    ).select_related('job', 'job__posted_by', 'job__posted_by__hr_profile')
    return render(request, 'recruitment/my_applications.html', {'applications': applications})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView
from django.db.models import Q, Count, Avg
from django.core.mail import send_mail
from django.utils import timezone
from django.http import HttpResponse

from .forms import (
    HRSignUpForm, CandidateSignUpForm,
    HRProfileForm, CandidateProfileForm,
    JobPostingForm, JobApplicationForm,
    ApplicationStatusForm, JobSearchForm,
    JobBiasCriteriaFormSet, InterviewProposeForm, MessageForm,
)
from .models import (
    CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication,
    ResumeParseResult, ApplicationMatchScore,
    JobBiasCriteria, ApplicationBiasResult, Notification, InterviewSlot, Message,
)
from .utils.resume_parser import parse_resume
from .utils.match_scorer import compute_match_score, score_skills_overlap, analyze_skill_gap
from .utils.bias_agent import run_bias_agent
from .utils.bias_detector import scan_job_description


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
        from django.urls import reverse
        user = self.request.user
        if user.is_hr:
            return reverse('hr_dashboard')
        elif user.is_candidate:
            return reverse('candidate_dashboard')
        return reverse('home')


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

    upcoming = InterviewSlot.objects.filter(
        application__job__posted_by=request.user,
        status=InterviewSlot.STATUS_BOOKED,
        start_time__gte=timezone.now()
    ).select_related('application', 'application__candidate', 'application__job')[:10]

    soon = InterviewSlot.objects.filter(
        application__job__posted_by=request.user,
        status=InterviewSlot.STATUS_BOOKED,
        start_time__range=(timezone.now(), timezone.now() + timezone.timedelta(hours=24))
    )
    for s in soon:
        t = f"Interview Tomorrow: {s.application.job.title}"
        l = f"/slots/{s.pk}/ics/"
        if not Notification.objects.filter(user=request.user, title=t, link=l).exists():
            Notification.objects.create(user=request.user, title=t, body="Reminder set for next 24h", link=l)

    context = {
        'job_postings': job_postings,
        'total_applications': total_applications,
        'open_jobs': open_jobs,
        'shortlisted': shortlisted,
        'upcoming_interviews': upcoming,
        'notifications': Notification.objects.filter(user=request.user, unread=True)[:5],
    }
    return render(request, 'recruitment/hr_dashboard.html', context)


@hr_required
def hr_analytics(request):
    jobs = JobPosting.objects.filter(posted_by=request.user).annotate(
        total_apps=Count('applications'),
        apps_applied=Count('applications', filter=Q(applications__status=JobApplication.STATUS_APPLIED)),
        apps_shortlisted=Count('applications', filter=Q(applications__status=JobApplication.STATUS_SHORTLISTED)),
        apps_interview=Count('applications', filter=Q(applications__status=JobApplication.STATUS_INTERVIEW)),
        apps_hired=Count('applications', filter=Q(applications__status=JobApplication.STATUS_HIRED)),
        apps_rejected=Count('applications', filter=Q(applications__status=JobApplication.STATUS_REJECTED)),
        apps_withdrawn=Count('applications', filter=Q(applications__status=JobApplication.STATUS_WITHDRAWN)),
    )
    # Average match score per job (via subquery join)
    avg_scores = (
        ApplicationMatchScore.objects
        .values('application__job_id')
        .annotate(avg=Avg('score'))
    )
    avg_map = {row['application__job_id']: round(row['avg'] or 0) for row in avg_scores}

    rows = []
    totals = {
        'total': 0, 'applied': 0, 'shortlisted': 0, 'interview': 0, 'hired': 0, 'rejected': 0, 'withdrawn': 0
    }
    for j in jobs:
        total = j.total_apps or 0
        applied = j.apps_applied or 0
        shortlisted = j.apps_shortlisted or 0
        interview = j.apps_interview or 0
        hired = j.apps_hired or 0
        rejected = j.apps_rejected or 0
        withdrawn = j.apps_withdrawn or 0
        totals['total'] += total
        totals['applied'] += applied
        totals['shortlisted'] += shortlisted
        totals['interview'] += interview
        totals['hired'] += hired
        totals['rejected'] += rejected
        totals['withdrawn'] += withdrawn
        rows.append({
            'job': j,
            'total': total,
            'applied': applied,
            'shortlisted': shortlisted,
            'interview': interview,
            'hired': hired,
            'rejected': rejected,
            'withdrawn': withdrawn,
            'avg_score': avg_map.get(j.id, 0),
            'shortlist_rate': round((shortlisted / total) * 100) if total else 0,
            'hire_rate': round((hired / total) * 100) if total else 0,
        })
    context = {'rows': rows, 'totals': totals}
    return render(request, 'recruitment/hr_analytics.html', context)


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
        bias_formset = JobBiasCriteriaFormSet(request.POST)
        if form.is_valid() and bias_formset.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.save()
            bias_formset.instance = job
            bias_formset.save()
            
            # Phase 3: Bias Detection
            warnings = scan_job_description(job.description)
            for w in warnings:
                messages.warning(request, f"Bias Warning: {w}")

            messages.success(request, f"Job '{job.title}' posted successfully!")
            return redirect('hr_dashboard')
    else:
        form = JobPostingForm()
        bias_formset = JobBiasCriteriaFormSet()
    return render(request, 'recruitment/job_form.html', {
        'form': form, 'bias_formset': bias_formset, 'action': 'Create'
    })


@hr_required
def job_edit(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    if request.method == 'POST':
        form = JobPostingForm(request.POST, instance=job)
        bias_formset = JobBiasCriteriaFormSet(request.POST, instance=job)
        if form.is_valid() and bias_formset.is_valid():
            form.save()
            bias_formset.save()

            # Phase 3: Bias Detection
            warnings = scan_job_description(job.description)
            for w in warnings:
                messages.warning(request, f"Bias Warning: {w}")

            messages.success(request, "Job updated successfully!")
            return redirect('hr_dashboard')
    else:
        form = JobPostingForm(instance=job)
        bias_formset = JobBiasCriteriaFormSet(instance=job)
    return render(request, 'recruitment/job_form.html', {
        'form': form, 'bias_formset': bias_formset, 'action': 'Edit', 'job': job
    })


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
    ).prefetch_related('match_score', 'bias_results__criterion').all()

    # Ensure Phase 3 data is populated for older applications:
    # - compute match score if missing
    # - run bias agent for missing results
    try:
        from .utils.match_scorer import compute_match_score
        from .utils.bias_agent import run_bias_agent
    except Exception:
        compute_match_score = None
        run_bias_agent = None

    criteria = list(job.bias_criteria.all())
    crit_count = len(criteria)

    for app in applications:
        # Backfill match score
        if compute_match_score and not hasattr(app, 'match_score'):
            try:
                from .models import ApplicationMatchScore
                score = compute_match_score(app)
                ApplicationMatchScore.objects.update_or_create(
                    application=app,
                    defaults={
                        'score': score,
                        'skill_overlap_pct': 0.0,
                        'text_similarity_pct': 0.0,
                    }
                )
            except Exception:
                pass
        # Backfill bias results (if fewer results than criteria)
        if run_bias_agent and crit_count:
            try:
                existing = getattr(app, 'bias_results', None)
                existing_count = existing.count() if existing is not None else 0
                if existing_count < crit_count:
                    run_bias_agent(app)
            except Exception:
                pass

    # Compute skills display (top 3 + extra count) for each application to avoid complex template logic
    for app in applications:
        skills = []
        try:
            skills.extend(app.candidate.candidate_profile.skills_list())
        except Exception:
            pass
        try:
            pr = app.candidate.candidate_profile.parse_result
            skills.extend(pr.parsed_skills_list())
        except Exception:
            pass
        # Deduplicate preserving order
        seen = set()
        ordered = []
        for s in skills:
            key = s.strip().lower()
            if key and key not in seen:
                seen.add(key)
                ordered.append(s)
        app.display_skills_top3 = ordered[:3]
        app.display_skills_extra_count = max(0, len(ordered) - 3)

    # Build a nested lookup: {app.pk: {criterion.pk: result}} for template use
    bias_criteria = list(job.bias_criteria.all())
    bias_results_map = {}
    for app in applications:
        results_by_criterion = {r.criterion_id: r for r in app.bias_results.all()}
        bias_results_map[app.pk] = results_by_criterion

    # Phase 3: Blind Review Mode
    blind_mode = request.GET.get('blind') in ('1', 'true', 'True')

    return render(request, 'recruitment/applicant_list.html', {
        'job': job,
        'applications': applications,
        'bias_criteria': bias_criteria,
        'bias_results_map': bias_results_map,
        'blind_mode': blind_mode,
        'applications_count': applications.count(),
        'applications_plural': '' if applications.count() == 1 else 's',
    })


@hr_required
def export_applicants_csv(request, pk):
    import csv
    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    applications = job.applications.select_related('candidate', 'candidate__candidate_profile').prefetch_related('match_score', 'bias_results')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="applicants_job_{job.id}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Candidate Name', 'Email', 'Status', 'Applied At',
        'Match Score', 'Experience Years', 'Skills', 'Bias Passed', 'Bias Failed'
    ])
    for app in applications:
        name = app.candidate.get_full_name() or app.candidate.username
        email = app.candidate.email
        status = app.get_status_display()
        applied = app.applied_at.strftime("%Y-%m-%d %H:%M")
        score = getattr(app.match_score, 'score', '')
        exp = getattr(getattr(app.candidate, 'candidate_profile', None), 'experience_years', '')
        # Merge skills from profile and parsed
        skills = []
        try:
            skills.extend(app.candidate.candidate_profile.skills_list())
        except Exception:
            pass
        try:
            skills.extend(app.candidate.candidate_profile.parse_result.parsed_skills_list())
        except Exception:
            pass
        seen = set()
        ordered = []
        for s in skills:
            k = s.strip().lower()
            if k and k not in seen:
                seen.add(k)
                ordered.append(s.strip())
        skills_str = ', '.join(ordered)
        # Bias summary
        passed = app.bias_results.filter(passed=True).count()
        failed = app.bias_results.filter(passed=False).count()
        writer.writerow([name, email, status, applied, score, exp, skills_str, passed, failed])
    return response

@hr_required
def application_update_status(request, pk):
    application = get_object_or_404(JobApplication, pk=pk, job__posted_by=request.user)
    if request.method == 'POST':
        form = ApplicationStatusForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"Status updated to '{application.get_status_display()}'.")
            try:
                Notification.objects.create(
                    user=application.candidate,
                    title="Application Status Updated",
                    body=f"Your application for {application.job.title} is now '{application.get_status_display()}'.",
                    link="/candidate/applications/"
                )
                send_mail(
                    subject="Application Status Updated",
                    message=f"Your application for {application.job.title} is now '{application.get_status_display()}'.",
                    from_email=None,
                    recipient_list=[application.candidate.email],
                    fail_silently=True,
                )
            except Exception:
                pass
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

            # Phase 3 Bias Agent — auto-evaluate against HR criteria
            try:
                run_bias_agent(application)
            except Exception:
                pass  # Best-effort; never block an application

            messages.success(request, f"Applied to '{job.title}' successfully! Good luck!")
            try:
                Notification.objects.create(
                    user=job.posted_by,
                    title="New Job Application",
                    body=f"{request.user.username} applied to {job.title}",
                    link=f"/hr/jobs/{job.pk}/applicants/"
                )
                Notification.objects.create(
                    user=request.user,
                    title="Application Submitted",
                    body=f"Your application to {job.title} was received.",
                    link="/candidate/applications/"
                )
                send_mail(
                    subject="New Application Received",
                    message=f"A candidate applied to {job.title}.",
                    from_email=None,
                    recipient_list=[job.posted_by.email],
                    fail_silently=True,
                )
            except Exception:
                pass
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

    upcoming = InterviewSlot.objects.filter(
        application__candidate=request.user,
        status=InterviewSlot.STATUS_BOOKED,
        start_time__gte=timezone.now()
    ).select_related('application', 'application__job')[:10]

    soon = InterviewSlot.objects.filter(
        application__candidate=request.user,
        status=InterviewSlot.STATUS_BOOKED,
        start_time__range=(timezone.now(), timezone.now() + timezone.timedelta(hours=24))
    )
    for s in soon:
        t = f"Interview Tomorrow: {s.application.job.title}"
        l = f"/slots/{s.pk}/ics/"
        if not Notification.objects.filter(user=request.user, title=t, link=l).exists():
            Notification.objects.create(user=request.user, title=t, body="Reminder set for next 24h", link=l)

    context = {
        'applications': applications,
        'status_counts': status_counts,
        'profile': profile,
        'profile_complete': profile_complete,
        'open_jobs_count': JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).count(),
        'parse_result': parse_result,
        'upcoming_interviews': upcoming,
        'notifications': Notification.objects.filter(user=request.user, unread=True)[:5],
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

    # Phase 3: Skills Gap Analysis
    for app in applications:
        req_skills = app.job.required_skills_list()
        # combine parsed skills (if any) and manual profile skills
        cand_skills = []
        try:
            cand_skills.extend(request.user.candidate_profile.skills_list())
        except Exception:
            pass
        try:
            cand_skills.extend(request.user.candidate_profile.parse_result.parsed_skills_list())
        except Exception:
            pass
        
        # Determine missing skills
        app.missing_skills = analyze_skill_gap(cand_skills, req_skills) if req_skills else []

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


# ── Phase 3: Bias Agent ───────────────────────────────────────────────────────

@hr_required
def run_bias_check_view(request, pk):
    """
    HR-triggered re-evaluation of all applicants for a job against its bias criteria.
    POST only. Redirects back to applicant_list.
    """
    if request.method != 'POST':
        return redirect('applicant_list', pk=pk)

    job = get_object_or_404(JobPosting, pk=pk, posted_by=request.user)
    criteria_count = job.bias_criteria.count()

    if criteria_count == 0:
        messages.warning(request, "No bias criteria defined for this job yet. Add criteria when editing the job.")
        return redirect('applicant_list', pk=pk)

    applications = job.applications.all()
    evaluated = 0
    for application in applications:
        try:
            run_bias_agent(application)
            evaluated += 1
        except Exception:
            pass

    messages.success(
        request,
        f"Bias check completed: evaluated {evaluated} applicant(s) against {criteria_count} criterion/criteria."
    )
    return redirect('applicant_list', pk=pk)


@hr_required
def propose_interview(request, pk):
    application = get_object_or_404(JobApplication, pk=pk, job__posted_by=request.user)
    if request.method == 'POST':
        form = InterviewProposeForm(request.POST)
        if form.is_valid():
            slots = [
                (form.cleaned_data.get('slot1_start'), form.cleaned_data.get('slot1_end')),
                (form.cleaned_data.get('slot2_start'), form.cleaned_data.get('slot2_end')),
                (form.cleaned_data.get('slot3_start'), form.cleaned_data.get('slot3_end')),
            ]
            created = 0
            for s, e in slots:
                if s and e:
                    InterviewSlot.objects.create(
                        application=application,
                        start_time=s,
                        end_time=e,
                        proposed_by=request.user
                    )
                    created += 1
            if created:
                try:
                    Notification.objects.create(
                        user=application.candidate,
                        title="Interview Slots Proposed",
                        body=f"{application.job.title}: New interview slots are available.",
                        link=f"/candidate/applications/{application.pk}/interview/"
                    )
                    send_mail(
                        subject="Interview Slots Proposed",
                        message=f"Please choose an interview slot for {application.job.title}.",
                        from_email=None,
                        recipient_list=[application.candidate.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
                messages.success(request, "Interview slots proposed.")
                return redirect('applicant_list', pk=application.job.pk)
    else:
        form = InterviewProposeForm()
    return render(request, 'recruitment/interview_propose.html', {'form': form, 'application': application})


@candidate_required
def candidate_interview_select(request, pk):
    application = get_object_or_404(JobApplication, pk=pk, candidate=request.user)
    slots = application.interview_slots.filter(status=InterviewSlot.STATUS_PROPOSED, start_time__gte=timezone.now())
    return render(request, 'recruitment/interview_select.html', {'application': application, 'slots': slots})


@candidate_required
def book_interview_slot(request, slot_id):
    slot = get_object_or_404(InterviewSlot, pk=slot_id, application__candidate=request.user, status=InterviewSlot.STATUS_PROPOSED)
    application = slot.application
    InterviewSlot.objects.filter(application=application, status=InterviewSlot.STATUS_PROPOSED).exclude(pk=slot.pk).update(status=InterviewSlot.STATUS_CANCELLED)
    slot.status = InterviewSlot.STATUS_BOOKED
    slot.booked_by = request.user
    slot.save()
    try:
        Notification.objects.create(
            user=application.job.posted_by,
            title="Interview Slot Booked",
            body=f"{request.user.username} booked an interview for {application.job.title}.",
            link=f"/hr/jobs/{application.job.pk}/applicants/"
        )
        send_mail(
            subject="Interview Slot Booked",
            message=f"The candidate booked an interview slot for {application.job.title}.",
            from_email=None,
            recipient_list=[application.job.posted_by.email],
            fail_silently=True,
        )
    except Exception:
        pass
    messages.success(request, "Interview slot booked.")
    return redirect('candidate_dashboard')


@login_required
def notifications_list(request):
    items = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
    return render(request, 'recruitment/notifications.html', {'items': items})


@login_required
def message_thread(request, pk):
    application = get_object_or_404(JobApplication, pk=pk)
    if not (request.user.is_hr and application.job.posted_by_id == request.user.id) and not (request.user.is_candidate and application.candidate_id == request.user.id):
        messages.error(request, "Access denied.")
        return redirect('home')
    msgs = application.messages.select_related('sender').all()
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(application=application, sender=request.user, text=form.cleaned_data['text'])
            other = application.job.posted_by if request.user != application.job.posted_by else application.candidate
            try:
                Notification.objects.create(
                    user=other,
                    title="New Message",
                    body=f"New message on {application.job.title}.",
                    link=f"/messages/{application.pk}/"
                )
            except Exception:
                pass
            return redirect('message_thread', pk=pk)
    else:
        form = MessageForm()
    return render(request, 'recruitment/messages.html', {'application': application, 'thread_messages': msgs, 'form': form})


# ── Phase 5: Calendar Integration ─────────────────────────────────────────────

@login_required
def slot_ics(request, slot_id: int):
    """
    Generate an .ics calendar file for a booked or proposed interview slot.
    Access restricted to the candidate on the application or the job's HR.
    """
    slot = get_object_or_404(InterviewSlot, pk=slot_id)
    application = slot.application
    user = request.user
    if not ((user.is_candidate and application.candidate_id == user.id) or (user.is_hr and application.job.posted_by_id == user.id)):
        messages.error(request, "Access denied.")
        return redirect('home')

    def fmt(dt):
        dt_utc = timezone.localtime(dt, timezone=timezone.utc)
        return dt_utc.strftime("%Y%m%dT%H%M%SZ")

    now_utc = timezone.now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = f"Interview: {application.job.title}"
    description = f"Interview for {application.job.title} on FairHire"
    uid = f"slot-{slot.id}@fairhire.local"

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//FairHire//Interview//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now_utc}\r\n"
        f"DTSTART:{fmt(slot.start_time)}\r\n"
        f"DTEND:{fmt(slot.end_time)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    resp = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="interview_slot_{slot.id}.ics"'
    return resp

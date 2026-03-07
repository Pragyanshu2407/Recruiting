from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from .models import (
    CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication,
    JobBiasCriteria, Message,
)
from django import forms
from django.forms import DateTimeInput


# ── Auth Forms ──────────────────────────────────────────────────────────────

class HRSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_hr = True
        if commit:
            user.save()
            HRProfile.objects.create(user=user)
        return user


class CandidateSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_candidate = True
        if commit:
            user.save()
            CandidateProfile.objects.create(user=user)
        return user


# ── Profile Forms ────────────────────────────────────────────────────────────

class HRProfileForm(forms.ModelForm):
    # Also allow editing first/last name from the same form
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = HRProfile
        fields = [
            'company_name', 'department', 'phone',
            'company_logo', 'company_website', 'company_description',
        ]
        widgets = {
            'company_description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        if commit:
            profile.save()
        return profile


class CandidateProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = CandidateProfile
        fields = [
            'bio', 'skills', 'experience_years', 'education', 'gender',
            'resume', 'linkedin_url', 'github_url', 'portfolio_url',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about yourself...'}),
            'skills': forms.TextInput(attrs={'placeholder': 'e.g. Python, Django, React, SQL'}),
            'education': forms.TextInput(attrs={'placeholder': 'e.g. B.Tech CSE, IIT Delhi'}),
            'gender': forms.TextInput(attrs={'placeholder': 'e.g. Male / Female / Non-binary / Prefer not to say'}),
        }
        labels = {
            'skills': 'Skills (comma-separated)',
            'gender': 'Gender (optional)',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        if commit:
            profile.save()
        return profile


# ── Job Posting Forms ─────────────────────────────────────────────────────────

class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            'title', 'description', 'required_skills', 'location',
            'location_type', 'salary_min', 'salary_max', 'deadline', 'status',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Describe the role, responsibilities, and requirements...'}),
            'required_skills': forms.TextInput(attrs={'placeholder': 'e.g. Python, Django, PostgreSQL'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Bangalore, India'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'salary_min': forms.NumberInput(attrs={'placeholder': '₹ Min (LPA)'}),
            'salary_max': forms.NumberInput(attrs={'placeholder': '₹ Max (LPA)'}),
        }
        labels = {
            'required_skills': 'Required Skills (comma-separated)',
            'salary_min': 'Min Salary (₹/year)',
            'salary_max': 'Max Salary (₹/year)',
        }


# ── Job Application Form ──────────────────────────────────────────────────────

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['cover_letter', 'resume_snapshot']
        widgets = {
            'cover_letter': forms.Textarea(
                attrs={'rows': 6, 'placeholder': 'Write a cover letter tailored to this role...'}
            ),
        }
        labels = {
            'resume_snapshot': 'Upload Resume (optional — uses your profile resume if not provided)',
        }


# ── Application Status Update Form (HR only) ──────────────────────────────────

class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['status', 'hr_notes']
        widgets = {
            'hr_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Internal notes (not visible to candidate)...'}),
        }


# ── Job Search / Filter Form ─────────────────────────────────────────────────

class JobSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search job title or skills...'}),
        label='Search',
    )
    location_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Locations')] + JobPosting.LOCATION_CHOICES,
        label='Work Mode',
    )
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Python, React'}),
        label='Filter by Skills',
    )


# ── Bias Criteria Forms (HR) ──────────────────────────────────────────

class JobBiasCriteriaForm(forms.ModelForm):
    """Single row in the bias criteria inline formset."""
    class Meta:
        model = JobBiasCriteria
        fields = ['criterion', 'value', 'description']
        widgets = {
            'criterion': forms.Select(attrs={'class': 'bias-criterion-select'}),
            'value': forms.TextInput(attrs={
                'placeholder': 'e.g. 5  /  3+  /  2-4  /  Tier 1  /  Female  /  keyword',
                'class': 'bias-value-input',
            }),
            'description': forms.TextInput(attrs={
                'placeholder': 'Optional label (shown to HR on applicant list)',
                'class': 'bias-desc-input',
            }),
        }
        labels = {
            'criterion':   'Rule Type',
            'value':       'Value',
            'description': 'Label (optional)',
        }


# Inline formset: up to 5 criteria per job posting
JobBiasCriteriaFormSet = inlineformset_factory(
    JobPosting,
    JobBiasCriteria,
    form=JobBiasCriteriaForm,
    extra=1,          # one empty row to start
    max_num=5,
    can_delete=True,
)


# ── Phase 4: Communication & Workflow ─────────────────────────────────────────

class InterviewProposeForm(forms.Form):
    slot1_start = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))
    slot1_end = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))
    slot2_start = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))
    slot2_end = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))
    slot3_start = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))
    slot3_end = forms.DateTimeField(required=False, widget=DateTimeInput(attrs={'type': 'datetime-local'}))

    def clean(self):
        cleaned = super().clean()
        pairs = [
            (cleaned.get('slot1_start'), cleaned.get('slot1_end')),
            (cleaned.get('slot2_start'), cleaned.get('slot2_end')),
            (cleaned.get('slot3_start'), cleaned.get('slot3_end')),
        ]
        provided = 0
        for s, e in pairs:
            if s or e:
                provided += 1
                if not s or not e or s >= e:
                    raise forms.ValidationError("Each slot must have a start before end.")
        if provided == 0:
            raise forms.ValidationError("Provide at least one time slot.")
        return cleaned


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type a message…'}),
        }

from django.contrib import admin
from .models import (
    CustomUser, HRProfile, CandidateProfile, JobPosting, JobApplication,
    ResumeParseResult, ApplicationMatchScore,
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_hr', 'is_candidate', 'date_joined', 'is_active')
    list_filter = ('is_hr', 'is_candidate', 'is_active')
    search_fields = ('username', 'email')


@admin.register(HRProfile)
class HRProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'department', 'phone')
    search_fields = ('user__username', 'company_name')


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience_years', 'education')
    search_fields = ('user__username', 'skills')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'posted_by', 'location_type', 'status', 'deadline', 'created_at')
    list_filter = ('status', 'location_type')
    search_fields = ('title', 'description')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'job', 'status', 'applied_at')
    list_filter = ('status',)
    search_fields = ('candidate__username', 'job__title')


@admin.register(ResumeParseResult)
class ResumeParseResultAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'parsed_experience_years', 'parsed_education', 'parsed_at')
    search_fields = ('candidate__user__username',)
    readonly_fields = ('raw_text', 'parsed_at')


@admin.register(ApplicationMatchScore)
class ApplicationMatchScoreAdmin(admin.ModelAdmin):
    list_display = ('application', 'score', 'skill_overlap_pct', 'text_similarity_pct', 'computed_at')
    list_filter = ('score',)
    readonly_fields = ('computed_at',)


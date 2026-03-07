from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # General
    path('', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('signup/hr/', views.HRSignUpView.as_view(), name='hr_signup'),
    path('signup/candidate/', views.CandidateSignUpView.as_view(), name='candidate_signup'),

    # HR
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),
    path('hr/profile/', views.hr_profile_edit, name='hr_profile'),
    path('hr/jobs/new/', views.job_create, name='job_create'),
    path('hr/jobs/<int:pk>/edit/', views.job_edit, name='job_edit'),
    path('hr/jobs/<int:pk>/delete/', views.job_delete, name='job_delete'),
    path('hr/jobs/<int:pk>/applicants/', views.applicant_list, name='applicant_list'),
    path('hr/jobs/<int:pk>/bias-check/', views.run_bias_check_view, name='run_bias_check'),
    path('hr/jobs/<int:pk>/export.csv', views.export_applicants_csv, name='export_applicants_csv'),
    path('hr/analytics/', views.hr_analytics, name='hr_analytics'),
    path('hr/applications/<int:pk>/status/', views.application_update_status, name='application_update_status'),
    path('hr/applications/<int:pk>/interview/propose/', views.propose_interview, name='propose_interview'),

    # Candidate
    path('candidate/dashboard/', views.candidate_dashboard, name='candidate_dashboard'),
    path('candidate/profile/', views.candidate_profile_edit, name='candidate_profile'),
    path('candidate/applications/', views.my_applications, name='my_applications'),
    path('candidate/parse-resume/', views.parse_resume_view, name='parse_resume'),
    path('candidate/applications/<int:pk>/interview/', views.candidate_interview_select, name='candidate_interview_select'),
    path('candidate/slots/<int:slot_id>/book/', views.book_interview_slot, name='book_interview_slot'),
    path('slots/<int:slot_id>/ics/', views.slot_ics, name='slot_ics'),

    # Public Job Board
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('jobs/<int:pk>/apply/', views.job_apply, name='job_apply'),
    path('notifications/', views.notifications_list, name='notifications'),
    path('messages/<int:pk>/', views.message_thread, name='message_thread'),
]

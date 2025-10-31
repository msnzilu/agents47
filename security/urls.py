"""
security/urls.py
URL Configuration for Security & Compliance (Phase 9)
"""
from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Security Dashboard
    path('dashboard/', views.SecurityDashboardView.as_view(), name='dashboard'),
    path('activity/', views.SecurityActivityView.as_view(), name='activity'),
    
    # Two-Factor Authentication
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/enable/', views.TwoFactorEnableView.as_view(), name='2fa_enable'),
    path('2fa/disable/', views.TwoFactorDisableView.as_view(), name='2fa_disable'),
    path('2fa/verify/', views.TwoFactorVerifyView.as_view(), name='2fa_verify'),
    
    # Privacy & GDPR
    path('privacy/', views.PrivacyDashboardView.as_view(), name='privacy_dashboard'),
    path('privacy/export/', views.DataExportRequestView.as_view(), name='data_export_request'),
    path('privacy/export/<int:request_id>/download/', views.DataExportDownloadView.as_view(), name='data_export_download'),
    path('privacy/delete/', views.DataDeletionRequestView.as_view(), name='data_deletion_request'),
    path('privacy/consent/', views.ConsentManagementView.as_view(), name='consent_management'),
    
    # API Keys
    path('api-keys/', views.APIKeyManagementView.as_view(), name='api_keys'),
    path('api-keys/create/', views.APIKeyCreateView.as_view(), name='api_key_create'),
    path('api-keys/<int:key_id>/revoke/', views.APIKeyRevokeView.as_view(), name='api_key_revoke'),
    
    # Admin (staff only)
    path('admin/deletion-review/', views.DataDeletionReviewView.as_view(), name='deletion_review'),
    path('admin/deletion/<int:request_id>/approve/', views.DataDeletionApproveView.as_view(), name='deletion_approve'),
    path('admin/deletion/<int:request_id>/reject/', views.DataDeletionRejectView.as_view(), name='deletion_reject'),
]
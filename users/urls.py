"""
URL patterns for users app.
"""
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('login/2fa/', views.Login2FAVerifyView.as_view(), name='login_2fa_verify'),
    path('login/2fa/cancel/', views.login_2fa_cancel, name='login_2fa_cancel'),
    path('logout/', views.custom_logout, name='logout'),

    path('contact/', views.contact_view, name='contact'),
    path('contact/submit/', views.contact_submit, name='contact_submit'),
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # Password Reset
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
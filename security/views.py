"""
Phase 9: Security & Compliance - Views
Security endpoints, 2FA setup, GDPR requests
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View, FormView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import PermissionDenied
import logging
from .models import (
    TwoFactorAuth, LoginAttempt, OAuth2Connection,
    DataExportRequest, DataDeletionRequest, ConsentRecord,
    DataRetentionPolicy, PasswordHistory
)
from .services import (
    setup_2fa_for_user, enable_2fa_for_user, disable_2fa_for_user,
    GDPRDataExporter, GDPRDataDeleter
)
from .middleware import rate_limit
from .validators import InputSanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# TWO-FACTOR AUTHENTICATION VIEWS
# =============================================================================

class TwoFactorSetupView(LoginRequiredMixin, TemplateView):
    """Setup 2FA for user account"""
    template_name = 'users/security/2fa_setup.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Setup 2FA if not exists
        if not hasattr(user, 'two_factor_auth'):
            two_factor = setup_2fa_for_user(user)
        else:
            two_factor = user.two_factor_auth
        
        context.update({
            'qr_code': two_factor.get_qr_code_image(),
            'secret_key': two_factor.secret_key,
            'backup_codes': two_factor.backup_codes if two_factor.backup_codes else []
        })
        
        return context


class TwoFactorEnableView(LoginRequiredMixin, View):
    """Enable 2FA after token verification"""
    
    def post(self, request):
        token = request.POST.get('token')
        
        if not token:
            return JsonResponse({'error': 'Token is required'}, status=400)
        
        # Enable 2FA
        success = enable_2fa_for_user(request.user, token)
        
        if success:
            messages.success(request, '2FA has been enabled successfully.')
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Invalid token'}, status=400)


class TwoFactorDisableView(LoginRequiredMixin, View):
    """Disable 2FA"""
    
    def post(self, request):
        password = request.POST.get('password')
        
        if not password:
            return JsonResponse({'error': 'Password is required'}, status=400)
        
        # Disable 2FA
        success = disable_2fa_for_user(request.user, password)
        
        if success:
            messages.success(request, '2FA has been disabled.')
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Invalid password'}, status=400)


class TwoFactorVerifyView(View):
    """Verify 2FA token during login"""
    
    def post(self, request):
        token = request.POST.get('token')
        user_id = request.session.get('2fa_user_id')
        
        if not user_id or not token:
            return JsonResponse({'error': 'Invalid request'}, status=400)
        
        from django.contrib.auth import get_user_model, login
        User = get_user_model()
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Verify token
        if hasattr(user, 'two_factor_auth'):
            if user.two_factor_auth.verify_token(token):
                # Login user
                login(request, user)
                del request.session['2fa_user_id']
                
                return JsonResponse({'success': True, 'redirect': '/'})
            else:
                # Check backup code
                if user.two_factor_auth.verify_backup_code(token):
                    login(request, user)
                    del request.session['2fa_user_id']
                    messages.warning(
                        request,
                        'You used a backup code. Please generate new backup codes.'
                    )
                    return JsonResponse({'success': True, 'redirect': '/'})
        
        return JsonResponse({'error': 'Invalid token'}, status=400)


# =============================================================================
# GDPR COMPLIANCE VIEWS
# =============================================================================

class PrivacyDashboardView(LoginRequiredMixin, TemplateView):
    """Privacy dashboard for GDPR compliance"""
    template_name = 'users/security/privacy_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get export requests
        export_requests = DataExportRequest.objects.filter(user=user)[:10]
        
        # Get deletion requests
        deletion_requests = DataDeletionRequest.objects.filter(user=user)[:10]
        
        # Get consent records
        consent_records = ConsentRecord.objects.filter(user=user).order_by('-timestamp')[:20]
        
        context.update({
            'export_requests': export_requests,
            'deletion_requests': deletion_requests,
            'consent_records': consent_records,
        })
        
        return context


class DataExportRequestView(LoginRequiredMixin, View):
    """Request data export (GDPR Article 15)"""
    
    @rate_limit(limit=5, period=3600)  # 5 requests per hour
    def post(self, request):
        user = request.user
        
        # Check for pending requests
        pending_requests = DataExportRequest.objects.filter(
            user=user,
            status__in=['pending', 'processing']
        )
        
        if pending_requests.exists():
            return JsonResponse({
                'error': 'You already have a pending export request'
            }, status=400)
        
        # Create export request
        export_request = DataExportRequest.objects.create(
            user=user,
            ip_address=self._get_client_ip(request)
        )
        
        # Queue export task
        from .tasks import process_data_export
        process_data_export.delay(export_request.id)
        
        messages.success(
            request,
            'Your data export request has been submitted. '
            'You will receive an email when it\'s ready.'
        )
        
        return JsonResponse({'success': True, 'request_id': export_request.id})
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DataExportDownloadView(LoginRequiredMixin, View):
    """Download data export file"""
    
    def get(self, request, request_id):
        export_request = get_object_or_404(
            DataExportRequest,
            id=request_id,
            user=request.user
        )
        
        # Check if completed
        if export_request.status != 'completed':
            messages.error(request, 'Export is not ready yet.')
            return redirect('security:privacy_dashboard')
        
        # Check if expired
        if export_request.expires_at and timezone.now() > export_request.expires_at:
            messages.error(request, 'This export has expired.')
            return redirect('security:privacy_dashboard')
        
        # Serve file
        import os
        if not os.path.exists(export_request.file_path):
            messages.error(request, 'Export file not found.')
            return redirect('security:privacy_dashboard')
        
        return FileResponse(
            open(export_request.file_path, 'rb'),
            as_attachment=True,
            filename=os.path.basename(export_request.file_path)
        )


class DataDeletionRequestView(LoginRequiredMixin, View):
    """Request account and data deletion (GDPR Article 17)"""
    
    def post(self, request):
        user = request.user
        reason = request.POST.get('reason', '')
        
        # Check for pending requests
        pending_requests = DataDeletionRequest.objects.filter(
            user=user,
            status__in=['pending', 'approved', 'processing']
        )
        
        if pending_requests.exists():
            return JsonResponse({
                'error': 'You already have a pending deletion request'
            }, status=400)
        
        # Create deletion request
        deletion_request = DataDeletionRequest.objects.create(
            user=user,
            reason=reason,
            ip_address=self._get_client_ip(request),
            delete_messages=True,
            delete_agents=True,
            delete_knowledge_base=True,
            delete_analytics=True
        )
        
        messages.warning(
            request,
            'Your deletion request has been submitted and will be reviewed. '
            'You will receive an email with further instructions.'
        )
        
        # Send email to admin
        from django.core.mail import mail_admins
        mail_admins(
            subject=f'Data Deletion Request from {user.email}',
            message=f'User {user.email} has requested account deletion.\n\nReason: {reason}'
        )
        
        return JsonResponse({'success': True, 'request_id': deletion_request.id})
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ConsentManagementView(LoginRequiredMixin, View):
    """Manage user consent preferences"""
    
    def post(self, request):
        user = request.user
        consent_type = request.POST.get('consent_type')
        consented = request.POST.get('consented') == 'true'
        version = settings.PRIVACY_POLICY_VERSION
        
        # Record consent
        ConsentRecord.record_consent(
            user=user,
            consent_type=consent_type,
            consented=consented,
            version=version,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        action = "granted" if consented else "revoked"
        messages.success(request, f'Consent {action} successfully.')
        
        return JsonResponse({'success': True})
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# =============================================================================
# SECURITY DASHBOARD
# =============================================================================

class SecurityDashboardView(LoginRequiredMixin, TemplateView):
    """Security settings dashboard"""
    template_name = 'users/security/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 2FA status
        has_2fa = hasattr(user, 'two_factor_auth')
        context['has_2fa'] = has_2fa
        context['2fa_enabled'] = has_2fa and user.two_factor_auth.is_enabled
        
        # Recent login attempts
        recent_logins = LoginAttempt.objects.filter(
            email=user.email
        ).order_by('-timestamp')[:10]
        context['recent_logins'] = recent_logins
        
        # OAuth connections
        if hasattr(user, 'security_oauth_connections'):
            context['oauth_connections'] = user.security_oauth_connections.all()
        
        # Security recommendations
        recommendations = []
        if not context['2fa_enabled']:
            recommendations.append({
                'severity': 'high',
                'title': 'Enable Two-Factor Authentication',
                'description': 'Add an extra layer of security to your account.',
                'action_url': '/security/2fa/setup/'
            })
        
        failed_logins = LoginAttempt.get_recent_failures(user.email, minutes=1440)  # 24 hours
        if failed_logins > 0:
            recommendations.append({
                'severity': 'warning',
                'title': f'{failed_logins} Failed Login Attempt(s)',
                'description': 'There were failed login attempts on your account.',
                'action_url': '/security/activity/'
            })
        
        context['recommendations'] = recommendations
        
        return context


class SecurityActivityView(LoginRequiredMixin, TemplateView):
    """View security activity log"""
    template_name = 'users/security/activity.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all login attempts
        attempts = LoginAttempt.objects.filter(
            email=user.email
        ).order_by('-timestamp')[:50]
        
        context['login_attempts'] = attempts
        
        return context


# =============================================================================
# API KEY MANAGEMENT
# =============================================================================

class APIKeyManagementView(LoginRequiredMixin, TemplateView):
    """Manage API keys"""
    template_name = 'users/security/api_keys.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's API keys
        from integrations.models import APIKey
        context['api_keys'] = APIKey.objects.filter(user=self.request.user)
        
        return context


class APIKeyCreateView(LoginRequiredMixin, View):
    """Create new API key"""
    
    def post(self, request):
        from integrations.models import APIKey
        import secrets
        
        name = request.POST.get('name', 'Default Key')
        
        # Generate key
        key = secrets.token_urlsafe(32)
        
        # Create API key
        api_key = APIKey.objects.create(
            user=request.user,
            name=name,
            key=key
        )
        
        messages.success(
            request,
            f'API key created successfully. Make sure to save it: {key}'
        )
        
        return JsonResponse({
            'success': True,
            'key': key,
            'id': api_key.id
        })


class APIKeyRevokeView(LoginRequiredMixin, View):
    """Revoke API key"""
    
    def post(self, request, key_id):
        from integrations.models import APIKey
        
        api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
        api_key.delete()
        
        messages.success(request, 'API key revoked successfully.')
        
        return JsonResponse({'success': True})


# =============================================================================
# ADMIN VIEWS FOR GDPR
# =============================================================================

class DataDeletionReviewView(LoginRequiredMixin, TemplateView):
    """Admin view to review deletion requests"""
    template_name = 'security/admin/deletion_review.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get pending deletion requests
        pending_requests = DataDeletionRequest.objects.filter(
            status='pending'
        ).order_by('requested_at')
        
        context['pending_requests'] = pending_requests
        
        return context


class DataDeletionApproveView(LoginRequiredMixin, View):
    """Approve deletion request"""
    
    def post(self, request, request_id):
        if not request.user.is_staff:
            raise PermissionDenied
        
        deletion_request = get_object_or_404(DataDeletionRequest, id=request_id)
        
        # Approve request
        deletion_request.approve(request.user)
        
        # Queue deletion task
        from .tasks import process_data_deletion
        process_data_deletion.delay(deletion_request.id)
        
        messages.success(request, 'Deletion request approved and queued.')
        
        return JsonResponse({'success': True})


class DataDeletionRejectView(LoginRequiredMixin, View):
    """Reject deletion request"""
    
    def post(self, request, request_id):
        if not request.user.is_staff:
            raise PermissionDenied
        
        deletion_request = get_object_or_404(DataDeletionRequest, id=request_id)
        reason = request.POST.get('reason', '')
        
        # Reject request
        deletion_request.reject(request.user, reason)
        
        messages.success(request, 'Deletion request rejected.')
        
        return JsonResponse({'success': True})
"""
Phase 9: Security & Compliance - Celery Tasks
Async tasks for data export, deletion, and cleanup
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_data_export(self, export_request_id):
    """Process GDPR data export request"""
    from .gdpr_compliance import DataExportRequest, GDPRDataExporter
    
    try:
        export_request = DataExportRequest.objects.get(id=export_request_id)
        export_request.mark_processing()
        
        # Export data
        exporter = GDPRDataExporter(export_request.user)
        file_path = exporter.generate_export_file(file_format='json')
        
        # Mark as completed
        export_request.mark_completed(file_path)
        
        # Send email notification
        send_mail(
            subject='Your Data Export is Ready',
            message=f'Your data export is ready for download. '
                   f'Visit {settings.SITE_URL}/security/privacy/export/{export_request.id}/download/ '
                   f'to download it. This link will expire in 7 days.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[export_request.user.email],
            fail_silently=False
        )
        
        logger.info(f"Data export completed for user {export_request.user.email}")
        
    except DataExportRequest.DoesNotExist:
        logger.error(f"Export request {export_request_id} not found")
    except Exception as e:
        logger.error(f"Error processing export {export_request_id}: {str(e)}")
        
        try:
            export_request = DataExportRequest.objects.get(id=export_request_id)
            export_request.mark_failed(str(e))
        except:
            pass
        
        # Retry
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def process_data_deletion(self, deletion_request_id):
    """Process GDPR data deletion request"""
    from .gdpr_compliance import DataDeletionRequest, GDPRDataDeleter
    
    try:
        deletion_request = DataDeletionRequest.objects.get(id=deletion_request_id)
        
        if deletion_request.status != 'approved':
            logger.warning(f"Deletion request {deletion_request_id} is not approved")
            return
        
        deletion_request.status = 'processing'
        deletion_request.save(update_fields=['status'])
        
        # Delete data
        deleter = GDPRDataDeleter(deletion_request.user)
        deleter.delete_all_data(deletion_request)
        
        # Send confirmation email (to original email before anonymization)
        original_email = deletion_request.user.email
        
        send_mail(
            subject='Your Account Has Been Deleted',
            message='Your account and associated data have been deleted as requested. '
                   'If you have any questions, please contact support.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[original_email],
            fail_silently=True
        )
        
        logger.info(f"Data deletion completed for user {original_email}")
        
    except DataDeletionRequest.DoesNotExist:
        logger.error(f"Deletion request {deletion_request_id} not found")
    except Exception as e:
        logger.error(f"Error processing deletion {deletion_request_id}: {str(e)}")
        
        try:
            deletion_request = DataDeletionRequest.objects.get(id=deletion_request_id)
            deletion_request.mark_failed(str(e))
        except:
            pass
        
        # Don't retry data deletion for safety
        raise


@shared_task
def cleanup_expired_exports():
    """Clean up expired data exports"""
    from .gdpr_compliance import DataExportRequest
    import os
    
    # Get expired exports
    expired = DataExportRequest.objects.filter(
        status='completed',
        expires_at__lt=timezone.now()
    )
    
    deleted_count = 0
    for export in expired:
        if export.file_path and os.path.exists(export.file_path):
            try:
                os.remove(export.file_path)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting export file {export.file_path}: {str(e)}")
        
        export.delete()
    
    logger.info(f"Cleaned up {deleted_count} expired exports")


@shared_task
def cleanup_old_login_attempts():
    """Clean up old login attempts"""
    from .authentication_enhancements import LoginAttempt
    from datetime import timedelta
    
    # Delete login attempts older than 90 days
    cutoff = timezone.now() - timedelta(days=90)
    deleted_count = LoginAttempt.objects.filter(timestamp__lt=cutoff).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old login attempts")


@shared_task
def cleanup_expired_data_retention():
    """Run data retention cleanup"""
    from .gdpr_compliance import cleanup_expired_data
    
    cleanup_expired_data()


@shared_task
def send_security_report():
    """Send weekly security report to admins"""
    from .authentication_enhancements import LoginAttempt
    from datetime import timedelta
    
    # Get stats for last 7 days
    week_ago = timezone.now() - timedelta(days=7)
    
    total_attempts = LoginAttempt.objects.filter(timestamp__gte=week_ago).count()
    failed_attempts = LoginAttempt.objects.filter(
        timestamp__gte=week_ago,
        success=False
    ).count()
    
    # Get accounts with multiple failures
    from django.db.models import Count
    problem_accounts = LoginAttempt.objects.filter(
        timestamp__gte=week_ago,
        success=False
    ).values('email').annotate(
        failure_count=Count('id')
    ).filter(failure_count__gte=5).order_by('-failure_count')[:10]
    
    # Format report
    report = f"""
    Security Report - Last 7 Days
    =============================
    
    Total Login Attempts: {total_attempts}
    Failed Attempts: {failed_attempts}
    Success Rate: {((total_attempts - failed_attempts) / max(total_attempts, 1) * 100):.1f}%
    
    Accounts with Multiple Failures:
    """
    
    for account in problem_accounts:
        report += f"\n- {account['email']}: {account['failure_count']} failures"
    
    # Send to admins
    from django.core.mail import mail_admins
    mail_admins(
        subject='Weekly Security Report',
        message=report
    )
    
    logger.info("Security report sent to admins")


@shared_task
def rotate_api_keys_warning():
    """Send warning for API keys that should be rotated"""
    from integrations.models import APIKey
    from datetime import timedelta
    
    # Keys older than 90 days
    rotation_threshold = timezone.now() - timedelta(days=90)
    old_keys = APIKey.objects.filter(created_at__lt=rotation_threshold, is_active=True)
    
    for api_key in old_keys:
        send_mail(
            subject='API Key Rotation Recommended',
            message=f'Your API key "{api_key.name}" is over 90 days old. '
                   f'For security, we recommend rotating it regularly. '
                   f'Visit {settings.SITE_URL}/security/api-keys/ to generate a new key.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[api_key.user.email],
            fail_silently=True
        )
    
    logger.info(f"Sent rotation warnings for {old_keys.count()} API keys")


@shared_task
def audit_security_settings():
    """Audit user security settings and send recommendations"""
    users_without_2fa = User.objects.filter(
        is_active=True,
        two_factor_auth__isnull=True
    ) | User.objects.filter(
        is_active=True,
        two_factor_auth__is_enabled=False
    )
    
    for user in users_without_2fa[:100]:  # Batch of 100
        send_mail(
            subject='Enhance Your Account Security',
            message='We noticed you haven\'t enabled Two-Factor Authentication yet. '
                   f'Visit {settings.SITE_URL}/security/2fa/setup/ to set it up and '
                   'add an extra layer of security to your account.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )
    
    logger.info(f"Sent security recommendations to {min(users_without_2fa.count(), 100)} users")
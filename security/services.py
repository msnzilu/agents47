"""
security/services.py
Complete services for Security & Compliance (Phase 9)
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import json
import csv
import zipfile
import io
import re
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# TWO-FACTOR AUTHENTICATION UTILITIES
# =============================================================================

def setup_2fa_for_user(user):
    """Setup 2FA for a user"""
    from .models import TwoFactorAuth
    
    # Check if already exists
    if hasattr(user, 'two_factor_auth'):
        return user.two_factor_auth
    
    # Create new 2FA
    secret_key = TwoFactorAuth.generate_secret_key()
    two_factor = TwoFactorAuth.objects.create(
        user=user,
        secret_key=secret_key
    )
    
    # Generate backup codes
    two_factor.generate_backup_codes()
    
    return two_factor


def enable_2fa_for_user(user, token: str) -> bool:
    """Enable 2FA after verifying initial token"""
    if not hasattr(user, 'two_factor_auth'):
        return False
    
    two_factor = user.two_factor_auth
    
    # Verify token
    if two_factor.verify_token(token):
        two_factor.is_enabled = True
        two_factor.save(update_fields=['is_enabled'])
        
        logger.info(f"2FA enabled for user {user.email}")
        return True
    
    return False


def disable_2fa_for_user(user, password: str) -> bool:
    """Disable 2FA after password verification"""
    if not user.check_password(password):
        return False
    
    if hasattr(user, 'two_factor_auth'):
        two_factor = user.two_factor_auth
        two_factor.is_enabled = False
        two_factor.save(update_fields=['is_enabled'])
        
        logger.info(f"2FA disabled for user {user.email}")
        return True
    
    return False


# =============================================================================
# GDPR DATA EXPORTER
# =============================================================================

class GDPRDataExporter:
    """Export user data in machine-readable format"""
    
    def __init__(self, user):
        self.user = user
    
    def export_all_data(self) -> dict:
        """Export all user data"""
        return {
            'user_profile': self.export_user_profile(),
            'agents': self.export_agents(),
            'conversations': self.export_conversations(),
            'knowledge_base': self.export_knowledge_base(),
            'analytics': self.export_analytics(),
            'audit_logs': self.export_audit_logs(),
            'export_metadata': {
                'exported_at': timezone.now().isoformat(),
                'export_version': '1.0',
                'user_id': str(self.user.id)
            }
        }
    
    def export_user_profile(self) -> dict:
        """Export user profile data"""
        return {
            'email': self.user.email,
            'name': self.user.get_full_name(),
            'date_joined': self.user.date_joined.isoformat() if hasattr(self.user, 'date_joined') else None,
            'last_login': self.user.last_login.isoformat() if self.user.last_login else None,
            'is_active': self.user.is_active,
        }
    
    def export_agents(self) -> list:
        """Export user's agents"""
        try:
            from agents.models import Agent
            agents = Agent.objects.filter(user=self.user)
            return [
                {
                    'id': str(agent.id),
                    'name': agent.name,
                    'description': agent.description,
                    'use_case': agent.use_case,
                    'created_at': agent.created_at.isoformat(),
                    'updated_at': agent.updated_at.isoformat(),
                }
                for agent in agents
            ]
        except ImportError:
            return []
    
    def export_conversations(self) -> list:
        """Export user's conversations"""
        try:
            from chat.models import Conversation
            conversations = Conversation.objects.filter(user=self.user).prefetch_related('messages')
            return [
                {
                    'id': str(conv.id),
                    'agent_id': str(conv.agent_id) if hasattr(conv, 'agent_id') else None,
                    'title': conv.title if hasattr(conv, 'title') else 'Conversation',
                    'created_at': conv.created_at.isoformat(),
                    'messages': [
                        {
                            'role': msg.role,
                            'content': msg.content,
                            'timestamp': msg.created_at.isoformat(),
                        }
                        for msg in conv.messages.all()
                    ]
                }
                for conv in conversations
            ]
        except ImportError:
            return []
    
    def export_knowledge_base(self) -> list:
        """Export knowledge base documents"""
        try:
            from agents.models import KnowledgeBase
            documents = KnowledgeBase.objects.filter(agent__user=self.user)
            return [
                {
                    'id': str(doc.id),
                    'title': doc.title if hasattr(doc, 'title') else 'Document',
                    'content': doc.content if hasattr(doc, 'content') else '',
                    'created_at': doc.created_at.isoformat(),
                }
                for doc in documents
            ]
        except ImportError:
            return []
    
    def export_analytics(self) -> dict:
        """Export analytics data"""
        try:
            from analytics.models import UsageLog
            usage_logs = UsageLog.objects.filter(user=self.user)
            return {
                'usage_summary': {
                    'total_api_calls': usage_logs.count(),
                    'total_tokens': sum(log.total_tokens or 0 for log in usage_logs),
                    'total_cost': float(sum(log.cost or 0 for log in usage_logs)),
                },
                'usage_logs': [
                    {
                        'timestamp': log.created_at.isoformat(),
                        'event_type': log.event_type if hasattr(log, 'event_type') else 'unknown',
                        'tokens': log.total_tokens if hasattr(log, 'total_tokens') else 0,
                        'cost': float(log.cost) if hasattr(log, 'cost') and log.cost else 0,
                    }
                    for log in usage_logs[:1000]  # Limit to last 1000
                ]
            }
        except ImportError:
            return {'usage_summary': {}, 'usage_logs': []}
    
    def export_audit_logs(self) -> list:
        """Export audit logs"""
        try:
            from analytics.models import AuditLog
            logs = AuditLog.objects.filter(user=self.user)
            return [
                {
                    'timestamp': log.created_at.isoformat(),
                    'action': log.action if hasattr(log, 'action') else 'unknown',
                    'object_type': log.object_type if hasattr(log, 'object_type') else 'unknown',
                    'ip_address': log.ip_address if hasattr(log, 'ip_address') else 'unknown',
                }
                for log in logs[:1000]  # Limit to last 1000
            ]
        except ImportError:
            return []
    
    def generate_export_file(self, file_format: str = 'json') -> str:
        """Generate export file and return path"""
        data = self.export_all_data()
        
        # Create export directory
        import os
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', str(self.user.id))
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        if file_format == 'json':
            file_path = os.path.join(export_dir, f'data_export_{timestamp}.json')
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        elif file_format == 'csv':
            # Create ZIP with multiple CSV files
            file_path = os.path.join(export_dir, f'data_export_{timestamp}.zip')
            with zipfile.ZipFile(file_path, 'w') as zipf:
                # User profile CSV
                self._add_csv_to_zip(zipf, 'user_profile.csv', [data['user_profile']])
                # Agents CSV
                if data['agents']:
                    self._add_csv_to_zip(zipf, 'agents.csv', data['agents'])
                # Conversations CSV
                if data['conversations']:
                    self._add_csv_to_zip(zipf, 'conversations.csv', data['conversations'])
        
        return file_path
    
    def _add_csv_to_zip(self, zipf, filename: str, data: list):
        """Add CSV file to ZIP archive"""
        if not data:
            return
        
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        zipf.writestr(filename, output.getvalue())


# =============================================================================
# GDPR DATA DELETER
# =============================================================================

class GDPRDataDeleter:
    """Delete user data per GDPR requirements"""
    
    def __init__(self, user):
        self.user = user
    
    def delete_all_data(self, deletion_request):
        """Delete all user data"""
        from .models import DataDeletionRequest
        
        try:
            if deletion_request.delete_messages:
                self.delete_conversations()
            
            if deletion_request.delete_agents:
                self.delete_agents()
            
            if deletion_request.delete_knowledge_base:
                self.delete_knowledge_base()
            
            if deletion_request.delete_analytics:
                self.anonymize_analytics()
            
            # Always anonymize audit logs (keep for compliance)
            self.anonymize_audit_logs()
            
            # Finally, anonymize user account
            self.anonymize_user_account()
            
            deletion_request.mark_completed()
            
            logger.info(f"Successfully deleted data for user {self.user.email}")
            
        except Exception as e:
            logger.error(f"Error deleting data for user {self.user.email}: {str(e)}")
            deletion_request.mark_failed(str(e))
            raise
    
    def delete_conversations(self):
        """Delete all conversations and messages"""
        try:
            from chat.models import Conversation
            Conversation.objects.filter(user=self.user).delete()
        except ImportError:
            pass
    
    def delete_agents(self):
        """Delete all agents"""
        try:
            from agents.models import Agent
            Agent.objects.filter(user=self.user).delete()
        except ImportError:
            pass
    
    def delete_knowledge_base(self):
        """Delete knowledge base documents"""
        try:
            from agents.models import KnowledgeBase
            KnowledgeBase.objects.filter(agent__user=self.user).delete()
        except ImportError:
            pass
    
    def anonymize_analytics(self):
        """Anonymize analytics data"""
        try:
            from analytics.models import UsageLog
            UsageLog.objects.filter(user=self.user).update(
                user=None,
                ip_address='0.0.0.0'
            )
        except ImportError:
            pass
    
    def anonymize_audit_logs(self):
        """Anonymize audit logs (keep for compliance)"""
        try:
            from analytics.models import AuditLog
            AuditLog.objects.filter(user=self.user).update(
                ip_address='0.0.0.0',
                user_agent='anonymized'
            )
        except ImportError:
            pass
    
    def anonymize_user_account(self):
        """Anonymize user account"""
        import uuid
        anonymous_id = uuid.uuid4().hex[:8]
        
        self.user.email = f"deleted_user_{anonymous_id}@deleted.local"
        self.user.first_name = "Deleted"
        self.user.last_name = "User"
        self.user.is_active = False
        self.user.save()


# =============================================================================
# PII ANONYMIZATION
# =============================================================================

class PIIAnonymizer:
    """Anonymize Personally Identifiable Information in logs"""
    
    @staticmethod
    def anonymize_email(email: str) -> str:
        """Anonymize email address"""
        if '@' not in email:
            return '[REDACTED]'
        
        local, domain = email.split('@')
        anonymized_local = local[0] + '***' + local[-1] if len(local) > 2 else '***'
        return f"{anonymized_local}@{domain}"
    
    @staticmethod
    def anonymize_ip(ip_address: str) -> str:
        """Anonymize IP address"""
        if not ip_address or ip_address == 'unknown':
            return '0.0.0.0'
        
        parts = ip_address.split('.')
        if len(parts) == 4:
            # IPv4: Keep first two octets
            return f"{parts[0]}.{parts[1]}.0.0"
        
        # IPv6 or other: return placeholder
        return '::0'
    
    @staticmethod
    def anonymize_name(name: str) -> str:
        """Anonymize person name"""
        if not name or len(name) < 2:
            return '[REDACTED]'
        
        return name[0] + '***'
    
    @staticmethod
    def anonymize_text(text: str, patterns: list = None) -> str:
        """Anonymize PII in text using patterns"""
        if not patterns:
            patterns = [
                (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
                (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]'),
                (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
            ]
        
        anonymized = text
        for pattern, replacement in patterns:
            anonymized = re.sub(pattern, replacement, anonymized)
        
        return anonymized


# =============================================================================
# DATA RETENTION CLEANUP
# =============================================================================

def cleanup_expired_data():
    """Clean up data based on retention policies"""
    from .models import DataRetentionPolicy
    
    try:
        from analytics.models import UsageLog
        
        # Clean up old usage logs
        retention_days = DataRetentionPolicy.get_retention_days('usage_logs')
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        deleted_count = UsageLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Deleted {deleted_count} expired usage logs")
    except ImportError:
        pass
    
    try:
        from analytics.models import AuditLog
        
        # Clean up old audit logs
        audit_retention_days = DataRetentionPolicy.get_retention_days('audit_logs')
        audit_cutoff = timezone.now() - timedelta(days=audit_retention_days)
        
        audit_deleted = AuditLog.objects.filter(
            created_at__lt=audit_cutoff
        ).delete()[0]
        
        logger.info(f"Deleted {audit_deleted} expired audit logs")
    except ImportError:
        pass
"""
Notification service layer
Handles notification creation and delivery
"""
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from .models import Notification, NotificationPreference
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications"""
    
    @staticmethod
    def notify_agent_created(agent):
        """Notify user when agent is created"""
        Notification.create_notification(
            user=agent.user,
            notification_type='agent_created',
            title='Agent created successfully',
            message=f'Your AI agent "{agent.name}" has been created and is ready to use.',
            priority='low',
            agent=agent,
            link_url=f'/agents/{agent.id}/',
            link_text='View Agent'
        )
    
    @staticmethod
    def notify_agent_cloned(agent):
        """Notify user when agent is created"""
        Notification.create_notification(
            user=agent.user,
            notification_type='agent_cloned',
            title='Agent has been cloned',
            message=f'Your AI agent "{agent.name}" has been cloned. A copy is now available.',
            priority='low',
            agent=agent,
            link_url=f'/agents/{agent.id}/',
            link_text='View Agent'
        )
    
    @staticmethod
    def notify_agent_deleted(agent):
        """Notify user when agent is created"""
        Notification.create_notification(
            user=agent.user,
            notification_type='agent_deleted',
            title='Agent has been deleted',
            message=f'Your AI agent "{agent.name}" has been deleted. Its no longer available.',
            priority='low',
            agent=agent,
            link_url=f'/agents/{agent.id}/',
            # link_text='View Agent'
        )
    
    @staticmethod
    def notify_agent_deployed(agent):
        """Notify user when agent is deployed"""
        Notification.create_notification(
            user=agent.user,
            notification_type='agent_deployed',
            title='Agent deployed successfully',
            message=f'Your AI agent "{agent.name}" is now live and running.',
            priority='medium',
            agent=agent,
            link_url=f'/agents/{agent.id}/',
            link_text='View Agent'
        )
    
    @staticmethod
    def notify_agent_error(agent, error_message):
        """Notify user when agent encounters an error"""
        Notification.create_notification(
            user=agent.user,
            notification_type='agent_error',
            title='Agent error detected',
            message=f'Your agent "{agent.name}" encountered an error: {error_message}',
            priority='high',
            agent=agent,
            link_url=f'/analytics/agent/{agent.id}/',
            link_text='View Details',
            metadata={'error': error_message}
        )
    
    @staticmethod
    def notify_escalation(conversation):
        """Notify user when conversation is escalated"""
        Notification.create_notification(
            user=conversation.agent.user,
            notification_type='escalation_triggered',
            title='Conversation escalated',
            message=f'A conversation in "{conversation.agent.name}" requires attention.',
            priority='critical',
            agent=conversation.agent,
            conversation=conversation,
            link_url=f'/chat/{conversation.id}/',
            link_text='View Conversation'
        )
    
    @staticmethod
    def notify_performance_alert(user, message):
        """Notify user about performance issues"""
        Notification.create_notification(
            user=user,
            notification_type='performance_alert',
            title='Performance Alert',
            message=message,
            priority='high',
            link_url='/analytics/performance/',
            link_text='View Performance'
        )
    
    @staticmethod
    def notify_document_processed(user, document_name, agent):
        """Notify user when document is processed"""
        Notification.create_notification(
            user=user,
            notification_type='document_processed',
            title='Document processed',
            message=f'Document "{document_name}" has been processed and added to your knowledge base.',
            priority='low',
            agent=agent,
            link_url=f'/agents/{agent.id}/',
            link_text='View Agent'
        )
    
    @staticmethod
    def notify_usage_limit(user, limit_type, current, maximum):
        """Notify user about usage limits"""
        Notification.create_notification(
            user=user,
            notification_type='usage_limit',
            title='Usage Limit Warning',
            message=f'You have used {current} of {maximum} {limit_type}.',
            priority='high',
            link_url='/users/profile/',
            link_text='Upgrade Plan'
        )
    
    @staticmethod
    def get_unread_count(user):
        """Get count of unread notifications"""
        return Notification.objects.filter(
            user=user,
            is_read=False,
            is_archived=False
        ).count()
    
    @staticmethod
    def get_recent_notifications(user, limit=10):
        """Get recent notifications for user"""
        return Notification.objects.filter(
            user=user,
            is_archived=False
        ).select_related('agent', 'conversation')[:limit]
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications as read for user"""
        Notification.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
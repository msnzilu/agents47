"""
Notification views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Notification
from .services import NotificationService


@login_required
def notification_list(request):
    """List all notifications"""
    notifications = Notification.objects.filter(
        user=request.user,
        is_archived=False
    ).select_related('agent', 'conversation')[:50]
    
    unread_count = NotificationService.get_unread_count(request.user)
    
    return render(request, 'users/notifications/notification_list.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })


@login_required
def notification_api(request):
    """API endpoint for getting notifications (for navbar)"""
    notifications = NotificationService.get_recent_notifications(request.user, limit=10)
    unread_count = NotificationService.get_unread_count(request.user)
    
    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id': n.id,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'icon_class': n.get_icon_class(),
                'icon_svg': n.get_icon_svg(),
                'link_url': n.link_url,
                'link_text': n.link_text,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'time_ago': _get_time_ago(n.created_at)
            }
            for n in notifications
        ]
    }
    
    return JsonResponse(data)


@require_POST
@login_required
def mark_as_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications:list')


@require_POST
@login_required
def mark_all_as_read(request):
    """Mark all notifications as read"""
    NotificationService.mark_all_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications:list')


@require_POST
@login_required
def archive_notification(request, notification_id):
    """Archive a notification"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.archive()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications:list')


def _get_time_ago(dt):
    """Get human-readable time ago"""
    from django.utils import timezone
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        return f"{diff.days} days ago"
    
    hours = diff.seconds // 3600
    if hours > 0:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    
    minutes = diff.seconds // 60
    if minutes > 0:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"
    
    return "just now"
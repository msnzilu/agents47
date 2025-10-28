"""
Webhook Management Views
Phase 7: Integration Layer
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import Webhook, WebhookDelivery
from agents.models import Agent


@login_required
def webhook_list(request):
    """List all webhooks for user"""
    webhooks = Webhook.objects.filter(user=request.user).select_related('agent')
    
    paginator = Paginator(webhooks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'webhooks': page_obj,
        'total_webhooks': webhooks.count(),
        'active_webhooks': webhooks.filter(is_active=True).count(),
    }
    return render(request, 'users/webhooks/webhook_list.html', context)


@login_required
def webhook_create(request):
    """Create new webhook"""
    if request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        agent_id = request.POST.get('agent')
        description = request.POST.get('description', '')
        events = request.POST.getlist('events')
        
        if not name or not url or not events:
            messages.error(request, 'Name, URL, and at least one event are required')
            return redirect('webhooks:webhook-create')
        
        try:
            agent = None
            if agent_id:
                agent = Agent.objects.get(id=agent_id, user=request.user)
            
            webhook = Webhook.objects.create(
                user=request.user,
                agent=agent,
                name=name,
                url=url,
                description=description,
                events=events
            )
            
            messages.success(request, f'Webhook "{webhook.name}" created successfully!')
            return redirect('webhooks:webhook-detail', pk=webhook.id)
        
        except Agent.DoesNotExist:
            messages.error(request, 'Invalid agent selected')
        except Exception as e:
            messages.error(request, f'Error creating webhook: {str(e)}')
    
    # GET request - show form
    agents = Agent.objects.filter(user=request.user, is_active=True)
    event_choices = Webhook.EVENT_CHOICES
    
    context = {
        'agents': agents,
        'event_choices': event_choices,
    }
    return render(request, 'users/webhooks/webhook_form.html', context)


@login_required
def webhook_detail(request, pk):
    """View webhook details and delivery history"""
    webhook = get_object_or_404(Webhook, id=pk, user=request.user)
    
    # Get recent deliveries
    deliveries = WebhookDelivery.objects.filter(webhook=webhook).order_by('-created_at')[:50]
    
    # Calculate success rate
    success_rate = 0
    if webhook.total_deliveries > 0:
        success_rate = (webhook.successful_deliveries / webhook.total_deliveries) * 100
    
    context = {
        'webhook': webhook,
        'deliveries': deliveries,
        'success_rate': round(success_rate, 1),
        'event_choices': Webhook.EVENT_CHOICES,
    }
    return render(request, 'users/webhooks/webhook_detail.html', context)


@login_required
def webhook_edit(request, pk):
    """Edit webhook"""
    webhook = get_object_or_404(Webhook, id=pk, user=request.user)
    
    if request.method == 'POST':
        webhook.name = request.POST.get('name', webhook.name)
        webhook.url = request.POST.get('url', webhook.url)
        webhook.description = request.POST.get('description', '')
        webhook.events = request.POST.getlist('events')
        
        agent_id = request.POST.get('agent')
        if agent_id:
            try:
                webhook.agent = Agent.objects.get(id=agent_id, user=request.user)
            except Agent.DoesNotExist:
                pass
        else:
            webhook.agent = None
        
        webhook.save()
        messages.success(request, f'Webhook "{webhook.name}" updated successfully!')
        return redirect('webhooks:webhook-detail', pk=webhook.id)
    
    # GET request - show form
    agents = Agent.objects.filter(user=request.user, is_active=True)
    event_choices = Webhook.EVENT_CHOICES
    
    context = {
        'webhook': webhook,
        'agents': agents,
        'event_choices': event_choices,
        'is_edit': True,
    }
    return render(request, 'users/webhooks/webhook_form.html', context)


@login_required
@require_http_methods(["POST"])
def webhook_delete(request, pk):
    """Delete webhook"""
    webhook = get_object_or_404(Webhook, id=pk, user=request.user)
    webhook_name = webhook.name
    webhook.delete()
    
    messages.success(request, f'Webhook "{webhook_name}" deleted successfully')
    return redirect('webhooks:webhook-list')


@login_required
@require_http_methods(["POST"])
def webhook_toggle(request, pk):
    """Toggle webhook active status"""
    webhook = get_object_or_404(Webhook, id=pk, user=request.user)
    webhook.is_active = not webhook.is_active
    webhook.save()
    
    status = 'activated' if webhook.is_active else 'deactivated'
    return JsonResponse({
        'success': True,
        'is_active': webhook.is_active,
        'message': f'Webhook {status}'
    })


@login_required
def webhook_deliveries(request):
    """View all webhook deliveries"""
    deliveries = WebhookDelivery.objects.filter(
        webhook__user=request.user
    ).select_related('webhook').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        deliveries = deliveries.filter(status=status_filter)
    
    paginator = Paginator(deliveries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'deliveries': page_obj,
        'status_filter': status_filter,
        'status_choices': WebhookDelivery.STATUS_CHOICES,
    }
    return render(request, 'users/webhooks/webhook_deliveries.html', context)


@login_required
@require_http_methods(["POST"])
def webhook_test(request, pk):
    """Test webhook by sending a test payload"""
    webhook = get_object_or_404(Webhook, id=pk, user=request.user)
    
    # Create test delivery
    test_payload = {
        'event': 'test',
        'webhook_id': str(webhook.id),
        'timestamp': timezone.now().isoformat(),
        'message': 'This is a test webhook delivery'
    }
    
    delivery = WebhookDelivery.objects.create(
        webhook=webhook,
        event_type='test',
        payload=test_payload
    )
    
    # Trigger async delivery (assuming you have Celery task)
    try:
        from .tasks import deliver_webhook
        deliver_webhook.delay(str(delivery.id))
        
        return JsonResponse({
            'success': True,
            'message': 'Test webhook queued for delivery',
            'delivery_id': str(delivery.id)
        })
    except ImportError:
        # Fallback if Celery not available
        return JsonResponse({
            'success': True,
            'message': 'Test webhook created (async delivery not configured)',
            'delivery_id': str(delivery.id)
        })
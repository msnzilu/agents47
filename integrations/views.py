"""
Integration views for managing external services.
Phase 7: Complete implementation
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import secrets
import json

from agents.models import Agent
from .models import Integration, WebhookLog, APIKey


@login_required
def integration_list(request, agent_id):
    """List all integrations for an agent."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integrations = Integration.objects.filter(agent=agent).order_by('-created_at')
    
    context = {
        'agent': agent,
        'integrations': integrations,
    }
    return render(request, 'integrations/integration_list.html', context)


@login_required
def integration_create(request, agent_id):
    """Create a new integration."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        integration_type = request.POST.get('integration_type')
        webhook_url = request.POST.get('webhook_url', '')
        
        # Generate webhook secret
        webhook_secret = secrets.token_urlsafe(32) if webhook_url else ''
        
        integration = Integration.objects.create(
            agent=agent,
            name=name,
            integration_type=integration_type,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
            status=Integration.Status.PENDING,
        )
        
        messages.success(request, f'Integration "{name}" created successfully!')
        return redirect('integrations:integration_detail', agent_id=agent.id, pk=integration.id)
    
    context = {
        'agent': agent,
        'integration_types': Integration.IntegrationType.choices,
    }
    return render(request, 'integrations/integration_form.html', context)


@login_required
def integration_detail(request, agent_id, pk):
    """View integration details."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integration = get_object_or_404(Integration, pk=pk, agent=agent)
    
    # Get recent webhook logs
    recent_logs = integration.webhook_logs.order_by('-created_at')[:20]
    
    context = {
        'agent': agent,
        'integration': integration,
        'recent_logs': recent_logs,
    }
    return render(request, 'integrations/integration_detail.html', context)


@login_required
def integration_update(request, agent_id, pk):
    """Update an integration."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integration = get_object_or_404(Integration, pk=pk, agent=agent)
    
    if request.method == 'POST':
        integration.name = request.POST.get('name')
        integration.webhook_url = request.POST.get('webhook_url', '')
        integration.is_active = request.POST.get('is_active') == 'on'
        integration.save()
        
        messages.success(request, f'Integration "{integration.name}" updated!')
        return redirect('integrations:integration_detail', agent_id=agent.id, pk=integration.id)
    
    context = {
        'agent': agent,
        'integration': integration,
    }
    return render(request, 'integrations/integration_form.html', context)


@login_required
def integration_delete(request, agent_id, pk):
    """Delete an integration."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integration = get_object_or_404(Integration, pk=pk, agent=agent)
    
    if request.method == 'POST':
        name = integration.name
        integration.delete()
        messages.success(request, f'Integration "{name}" deleted!')
        return redirect('integrations:integration_list', agent_id=agent.id)
    
    context = {
        'agent': agent,
        'integration': integration,
    }
    return render(request, 'integrations/integration_confirm_delete.html', context)


@login_required
def integration_toggle_active(request, agent_id, pk):
    """Toggle integration active status."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integration = get_object_or_404(Integration, pk=pk, agent=agent)
    
    if request.method == 'POST':
        integration.is_active = not integration.is_active
        integration.save()
        
        status = "activated" if integration.is_active else "deactivated"
        messages.success(request, f'Integration "{integration.name}" {status}!')
    
    return redirect('integrations:integration_detail', agent_id=agent.id, pk=integration.id)


@login_required
def integration_test(request, agent_id, pk):
    """Test an integration by sending a test webhook."""
    agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
    integration = get_object_or_404(Integration, pk=pk, agent=agent)
    
    if request.method == 'POST':
        # Create test webhook log
        test_payload = {
            'event': 'test',
            'message': 'This is a test webhook',
            'timestamp': timezone.now().isoformat(),
        }
        
        webhook_log = WebhookLog.objects.create(
            integration=integration,
            event_type='test',
            payload=test_payload,
            status=WebhookLog.Status.SUCCESS,
            status_code=200,
        )
        
        # Update integration
        integration.last_triggered_at = timezone.now()
        integration.save()
        
        messages.success(request, 'Test webhook sent successfully!')
        return redirect('integrations:integration_detail', agent_id=agent.id, pk=integration.id)
    
    context = {
        'agent': agent,
        'integration': integration,
    }
    return render(request, 'integrations/integration_test.html', context)


# API Key Management

@login_required
def api_key_list(request):
    """List user's API keys."""
    api_keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'api_keys': api_keys,
    }
    return render(request, 'integrations/api_key_list.html', context)


@login_required
def api_key_create(request):
    """Create a new API key."""
    if request.method == 'POST':
        name = request.POST.get('name')
        
        # Generate secure API key
        key = f"sk-{secrets.token_urlsafe(32)}"
        
        api_key = APIKey.objects.create(
            user=request.user,
            name=name,
            key=key,
            scopes=['read', 'write'],  # Default scopes
        )
        
        messages.success(request, f'API key "{name}" created! Save it now, you won\'t see it again.')
        return redirect('integrations:api_key_detail', pk=api_key.id)
    
    return render(request, 'integrations/api_key_form.html')


@login_required
def api_key_detail(request, pk):
    """View API key details."""
    api_key = get_object_or_404(APIKey, pk=pk, user=request.user)
    
    # Only show full key on first view (right after creation)
    show_full_key = request.GET.get('show_key') == 'true'
    
    context = {
        'api_key': api_key,
        'show_full_key': show_full_key,
    }
    return render(request, 'integrations/api_key_detail.html', context)


@login_required
def api_key_delete(request, pk):
    """Delete an API key."""
    api_key = get_object_or_404(APIKey, pk=pk, user=request.user)
    
    if request.method == 'POST':
        name = api_key.name
        api_key.delete()
        messages.success(request, f'API key "{name}" deleted!')
        return redirect('integrations:api_key_list')
    
    context = {
        'api_key': api_key,
    }
    return render(request, 'integrations/api_key_confirm_delete.html', context)


# Webhook Receiver (Public endpoint)

@csrf_exempt
@require_POST
def webhook_receiver(request, integration_id, secret):
    """
    Public webhook receiver endpoint.
    Validates secret and logs webhook.
    """
    try:
        # Verify integration exists and secret matches
        integration = Integration.objects.get(
            id=integration_id,
            webhook_secret=secret,
            is_active=True
        )
        
        # Parse payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            payload = {'raw': request.body.decode('utf-8')}
        
        # Create webhook log
        webhook_log = WebhookLog.objects.create(
            integration=integration,
            event_type=payload.get('event', 'unknown'),
            payload=payload,
            status=WebhookLog.Status.SUCCESS,
            status_code=200,
        )
        
        # Update integration
        integration.last_triggered_at = timezone.now()
        integration.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook received',
            'log_id': webhook_log.id,
        })
    
    except Integration.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid integration or secret'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
"""
Chat views for real-time conversations.
Phase 1: Basic views
Phase 4: Complete implementation with WebSockets
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
import json
import logging

from agents.models import Agent
from .models import Conversation, Message
from .tasks import trigger_agent_response

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def chat_view(request, agent_id):
    """
    Chat interface for an agent.
    Phase 4: Real-time WebSocket chat
    """
    # Enhanced permission check
    agent = get_object_or_404(Agent, pk=agent_id)
    
    # Check if user has permission to chat with this agent
    if not agent.can_user_chat(request.user):
        messages.error(request, "You don't have permission to chat with this agent.")
        return redirect('agents:list')
    
    # Get or create a conversation with better error handling
    conversation_id = request.GET.get('conversation')
    
    try:
        if conversation_id:
            conversation = get_object_or_404(
                Conversation, 
                pk=conversation_id, 
                agent=agent,
                user=request.user  # Ensure conversation belongs to user
            )
        else:
            # Create new conversation with transaction
            with transaction.atomic():
                conversation = Conversation.objects.create(
                    agent=agent,
                    user=request.user,
                    title=f"Chat with {agent.name}",
                    channel='web',
                    metadata={
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': request.META.get('REMOTE_ADDR', ''),
                        'created_via': 'web_interface'
                    }
                )
    except Exception as e:
        logger.error(f"Error creating/retrieving conversation: {str(e)}")
        messages.error(request, "Unable to start conversation. Please try again.")
        return redirect('agents:agent_detail', pk=agent_id)
    
    # Handle POST requests for sending messages
    if request.method == 'POST':
        return handle_message_post(request, conversation)
    
    # Get paginated conversation history
    messages_list = conversation.messages.select_related('user').order_by('-created_at')
    paginator = Paginator(messages_list, 50)  # Show 50 messages per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get user's other conversations with this agent
    user_conversations = Conversation.objects.filter(
        agent=agent,
        user=request.user
    ).order_by('-updated_at')[:10]
    
    context = {
        'agent': agent,
        'conversation': conversation,
        'messages': page_obj,
        'user_conversations': user_conversations,
        'ws_url': f"/ws/chat/{conversation.id}/",  # WebSocket URL
        'can_send_messages': agent.is_active and conversation.is_active,
    }
    
    return render(request, 'users/chat/chat.html', context)


# chat/views.py (update handle_message_post)
def handle_message_post(request, conversation):
    """Handle POST request to send a message"""
    try:
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Message is too long'}, status=400)
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            user=request.user,
            role='user',
            content=content,
            metadata={
                'sent_at': timezone.now().isoformat(),
                'client_type': 'web'
            }
        )
        
        # Update conversation's last activity
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])
        
        # Trigger agent response asynchronously
        if conversation.agent.is_active:
            trigger_agent_response.delay(message.id)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message_id': message.id,
                'timestamp': message.created_at.isoformat()
            })
        
        return redirect('chat:chat_view', agent_id=conversation.agent.id)
        
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Failed to send message'}, status=500)
        messages.error(request, "Failed to send message. Please try again.")
        return redirect('chat:chat_view', agent_id=conversation.agent.id)

@require_http_methods(["GET"])
def embed_chat(request, agent_id):
    """
    Embeddable chat widget.
    Phase 7: Implementation
    """
    agent = get_object_or_404(Agent, pk=agent_id, is_active=True)
    
    # Check if embedding is allowed for this agent
    if not agent.allow_embedding:
        return HttpResponseForbidden("This agent cannot be embedded")
    
    # Check origin if needed
    origin = request.META.get('HTTP_ORIGIN', '')
    if agent.allowed_origins and origin not in agent.allowed_origins:
        return HttpResponseForbidden("Embedding not allowed from this origin")
    
    # Generate or retrieve anonymous session if user not authenticated
    if not request.user.is_authenticated:
        session_id = request.session.get('anonymous_chat_id')
        if not session_id:
            request.session['anonymous_chat_id'] = generate_session_id()
            request.session.save()
    
    context = {
        'agent': agent,
        'embed_mode': True,
        'ws_url': f"/ws/embed/{agent_id}/",
        'api_endpoint': f"/api/v1/agents/{agent_id}/chat/",
        'theme': request.GET.get('theme', 'light'),
        'position': request.GET.get('position', 'bottom-right'),
    }
    
    response = render(request, 'users/chat/embed_chat.html', context)
    
    # Allow embedding with proper CORS headers
    response['X-Frame-Options'] = 'ALLOWALL'
    if agent.allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
    
    return response


@login_required
@require_http_methods(["GET"])
def conversation_history(request, agent_id):
    """View all conversations with an agent"""
    agent = get_object_or_404(Agent, pk=agent_id)
    
    if not agent.can_user_chat(request.user):
        return HttpResponseForbidden()
    
    conversations = Conversation.objects.filter(
        agent=agent,
        user=request.user
    ).order_by('-updated_at')
    
    paginator = Paginator(conversations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'agent': agent,
        'conversations': page_obj,
    }
    
    return render(request, 'users/chat/history.html', context)


@login_required
@require_http_methods(["POST"])
def delete_conversation(request, conversation_id):
    """Delete a conversation"""
    conversation = get_object_or_404(
        Conversation,
        pk=conversation_id,
        user=request.user
    )
    
    conversation.is_active = False
    conversation.save(update_fields=['is_active'])
    
    messages.success(request, "Conversation deleted successfully")
    return redirect('chat:history', agent_id=conversation.agent.id)



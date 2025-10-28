from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def slack_webhook(request):
    """Handle incoming Slack messages"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    data = json.loads(request.body)
    
    # Handle Slack URL verification
    if data.get('type') == 'url_verification':
        return JsonResponse({'challenge': data['challenge']})
    
    # Handle events
    if data.get('type') == 'event_callback':
        event = data['event']
        
        if event['type'] == 'message' and not event.get('bot_id'):
            # Process user message
            process_slack_message(event)
    
    return JsonResponse({'status': 'ok'})

def process_slack_message(event):
    """Process incoming Slack message"""
    from chat.models import Conversation, Message
    from agents.models import Agent
    
    channel_id = event['channel']
    user_id = event['user']
    text = event['text']
    
    # Find agent configured for this Slack channel
    agent = Agent.objects.filter(
        integrations__integration_type='slack',
        integrations__settings__channel_id=channel_id,
        integrations__is_active=True
    ).first()
    
    if not agent:
        logger.warning(f"No agent found for Slack channel {channel_id}")
        return
    
    # Get or create conversation
    conversation, _ = Conversation.objects.get_or_create(
        agent=agent,
        channel='slack',
        channel_identifier=f"{channel_id}:{user_id}",
        defaults={'title': f'Slack conversation with {user_id}'}
    )
    
    # Create message
    Message.objects.create(
        conversation=conversation,
        role='user',
        content=text,
        metadata={
            'channel': channel_id,
            'user': user_id,
            'timestamp': event.get('ts')
        }
    )
    
    # Trigger agent response
    from chat.tasks import trigger_agent_response
    trigger_agent_response.delay(conversation.id, text)
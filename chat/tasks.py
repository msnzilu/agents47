# chat/tasks.py
from celery import shared_task
from .models import Message, Conversation
from agents.agents import AgentFactory
import logging

logger = logging.getLogger(__name__)

@shared_task
def trigger_agent_response(message_id):
    """Process agent response asynchronously."""
    try:
        message = Message.objects.get(id=message_id)
        conversation = message.conversation
        agent = conversation.agent
        
        if not agent.is_active:
            logger.warning(f"Agent {agent.id} is inactive")
            return
        
        langchain_agent = AgentFactory.create_agent(agent)
        response = AgentFactory.execute_agent(langchain_agent, message.content)
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response,
            metadata={
                'sent_at': timezone.now().isoformat(),
                'client_type': 'web'
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to process agent response: {str(e)}")
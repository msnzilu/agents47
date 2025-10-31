"""
Customer Support Tools for Phase 6.
Handles sentiment analysis, escalation detection, ticket creation, and canned responses.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from agents.tools.base import BaseTool, tool

logger = logging.getLogger(__name__)


@tool(name="sentiment_analyzer", use_cases=["support"])
class SentimentAnalyzer(BaseTool):
    """Analyzes customer message sentiment and emotional tone."""
    
    async def _execute(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of customer message."""
        text_lower = text.lower()
        
        negative_words = ['angry', 'frustrated', 'terrible', 'awful', 'hate', 'worst', 'unacceptable']
        positive_words = ['happy', 'great', 'excellent', 'love', 'thank', 'appreciate']
        
        negative_count = sum(1 for word in negative_words if word in text_lower)
        positive_count = sum(1 for word in positive_words if word in text_lower)
        
        score = (positive_count - negative_count) / max(len(text.split()), 1)
        score = max(-1.0, min(1.0, score))
        
        if score < -0.3:
            sentiment = 'negative'
        elif score > 0.3:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'sentiment_score': score,
            'confidence': abs(score)
        }


@tool(name="escalation_detector", use_cases=["support"])
class EscalationDetector(BaseTool):
    """Detects when customer issues should be escalated to human agents."""
    
    async def _execute(self, conversation_history: List[Dict], sentiment_score: float = 0) -> Dict[str, Any]:
        """Determine if issue should be escalated."""
        escalation_keywords = ['manager', 'supervisor', 'escalate', 'legal', 'lawyer', 'refund']
        
        should_escalate = False
        reason = []
        
        if sentiment_score < -0.7:
            should_escalate = True
            reason.append('Very negative sentiment detected')
        
        last_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        for msg in last_messages:
            content = msg.get('content', '').lower()
            if any(keyword in content for keyword in escalation_keywords):
                should_escalate = True
                reason.append('Escalation keywords detected')
                break
        
        if len(conversation_history) > 10:
            should_escalate = True
            reason.append('Extended conversation without resolution')
        
        return {
            'should_escalate': should_escalate,
            'reason': ', '.join(reason) if reason else 'No escalation needed',
            'priority': 'high' if should_escalate else 'normal'
        }


@tool(name="ticket_creator", use_cases=["support"])
class TicketCreator(BaseTool):
    """Creates support tickets in ticketing systems."""
    
    async def _execute(self, customer_id: str, issue_summary: str, 
                      priority: str = 'normal', category: str = 'general') -> Dict[str, Any]:
        """Create a support ticket."""
        ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        ticket = {
            'id': ticket_id,
            'customer_id': customer_id,
            'summary': issue_summary,
            'priority': priority,
            'category': category,
            'status': 'open',
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"Created ticket: {ticket_id}")
        
        return {
            'success': True,
            'ticket': ticket,
            'message': f"Ticket {ticket_id} created successfully"
        }


@tool(name="canned_response_suggester", use_cases=["support"])
class CannedResponseSuggester(BaseTool):
    """Suggests appropriate canned responses based on issue type."""
    
    CANNED_RESPONSES = {
        'billing': "I understand your billing concern. Let me help you with that right away.",
        'technical': "I'm sorry you're experiencing technical difficulties. Let's troubleshoot this together.",
        'shipping': "I can help you track your order and resolve any shipping issues.",
        'return': "I'll be happy to assist you with the return process.",
        'general': "Thank you for contacting us. How can I help you today?"
    }
    
    async def _execute(self, issue_category: str) -> Dict[str, Any]:
        """Suggest canned response for issue category."""
        response = self.CANNED_RESPONSES.get(issue_category, self.CANNED_RESPONSES['general'])
        
        return {
            'suggested_response': response,
            'category': issue_category,
            'alternatives': [v for k, v in self.CANNED_RESPONSES.items() if k != issue_category][:2]
        }


__all__ = [
    'SentimentAnalyzer',
    'EscalationDetector',
    'TicketCreator',
    'CannedResponseSuggester'
]
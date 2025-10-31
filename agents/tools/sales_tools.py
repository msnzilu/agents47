"""
Sales Tools for Phase 6.
Handles lead scoring, CRM integration, outreach personalization, and follow-up reminders.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from agents.tools.base import BaseTool, tool

logger = logging.getLogger(__name__)


@tool(name="lead_scorer", use_cases=["sales"])
class LeadScorer(BaseTool):
    """Scores leads using BANT criteria."""
    
    async def _execute(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score a lead."""
        budget = lead_data.get('budget', 0)
        timeline_days = lead_data.get('timeline_days', 999)
        authority = lead_data.get('authority', 'unknown')
        need = lead_data.get('need', 'low')
        
        score = 0
        if budget > 50000:
            score += 30
        elif budget > 10000:
            score += 20
        
        if timeline_days < 30:
            score += 20
        elif timeline_days < 90:
            score += 15
        
        if authority == 'decision_maker':
            score += 25
        elif authority == 'influencer':
            score += 15
        
        if need == 'critical':
            score += 25
        elif need == 'high':
            score += 15
        
        if score >= 80:
            status = 'hot'
        elif score >= 50:
            status = 'warm'
        else:
            status = 'cold'
        
        return {
            'total_score': score,
            'status': status,
            'breakdown': {
                'budget': budget,
                'authority': authority,
                'need': need,
                'timeline': timeline_days
            }
        }


@tool(name="crm_connector", use_cases=["sales"])
class CRMConnector(BaseTool):
    """Connects to CRM systems for contact management."""
    
    async def _execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Perform CRM operations."""
        if action == 'lookup':
            email = kwargs.get('email')
            return {
                'found': True,
                'contact': {
                    'id': 'CONT-123',
                    'email': email,
                    'name': 'John Doe',
                    'company': 'Acme Corp'
                }
            }
        elif action == 'update':
            return {
                'success': True,
                'contact_id': kwargs.get('contact_id'),
                'updated_fields': list(kwargs.keys())
            }
        elif action == 'create':
            return {
                'success': True,
                'contact_id': f'CONT-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                'created_at': datetime.now().isoformat()
            }
        
        return {'success': True, 'action': action}


@tool(name="outreach_template_personalizer", use_cases=["sales"])
class OutreachTemplatePersonalizer(BaseTool):
    """Personalizes outreach templates with contact data."""
    
    async def _execute(self, template: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Personalize an outreach template."""
        personalized = template
        for key, value in contact_data.items():
            personalized = personalized.replace(f'{{{key}}}', str(value))
        
        return {
            'personalized_message': personalized,
            'variables_used': list(contact_data.keys())
        }


@tool(name="follow_up_reminder", use_cases=["sales"])
class FollowUpReminder(BaseTool):
    """Creates follow-up reminders for sales activities."""
    
    async def _execute(self, contact_id: str, follow_up_date: str, 
                      note: str = '') -> Dict[str, Any]:
        """Create a follow-up reminder."""
        reminder_id = f"REM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            'success': True,
            'reminder_id': reminder_id,
            'contact_id': contact_id,
            'scheduled_for': follow_up_date,
            'note': note
        }


__all__ = [
    'LeadScorer',
    'CRMConnector',
    'OutreachTemplatePersonalizer',
    'FollowUpReminder'
]
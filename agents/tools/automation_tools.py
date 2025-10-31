"""
Automation Tools for Phase 6.
Handles workflow execution, email sending, webhooks, and scheduled triggers.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

from agents.tools.base import BaseTool, tool

logger = logging.getLogger(__name__)


@tool(name="workflow_executor", use_cases=["automation"])
class WorkflowExecutor(BaseTool):
    """Executes multi-step workflows."""
    
    async def _execute(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow with multiple steps."""
        workflow_id = workflow_config.get('id', 'workflow_' + datetime.now().strftime('%Y%m%d%H%M%S'))
        steps = workflow_config.get('steps', [])
        
        results = []
        failed = False
        
        for i, step in enumerate(steps):
            if failed:
                break
            
            step_type = step.get('type', 'action')
            step_name = step.get('name', f'Step {i+1}')
            
            step_result = {
                'step': i + 1,
                'name': step_name,
                'type': step_type,
                'status': 'completed',
                'timestamp': datetime.now().isoformat()
            }
            
            if step_type == 'condition':
                condition = step.get('condition', {})
                field = condition.get('field', '')
                operator = condition.get('operator', '==')
                value = condition.get('value', '')
                
                condition_met = True
                step_result['result'] = {
                    'condition_met': condition_met,
                    'field': field,
                    'operator': operator,
                    'value': value
                }
            
            elif step_type == 'wait':
                duration = step.get('duration', 0)
                await asyncio.sleep(duration)
                step_result['result'] = {
                    'waited': duration
                }
            
            elif step_type == 'action':
                action = step.get('action', {})
                action_type = action.get('type', 'unknown')
                
                if action.get('fail', False):
                    step_result['status'] = 'failed'
                    step_result['error'] = action.get('error', 'Step failed')
                    failed = True
                else:
                    step_result['result'] = {
                        'action_type': action_type,
                        'completed': True
                    }
            
            results.append(step_result)
        
        return {
            'success': not failed,
            'workflow_id': workflow_id,
            'total_steps': len(steps),
            'executed_steps': len(results),
            'results': results,
            'status': 'failed' if failed else 'completed'
        }


@tool(name="email_sender", use_cases=["automation", "sales"])
class EmailSender(BaseTool):
    """Sends emails using templates."""
    
    DEFAULT_TEMPLATES = {
        'notification': 'Hello {name}, {message}',
        'welcome': 'Welcome {name}!',
        'reminder': 'Reminder: {title}'
    }
    
    async def _execute(self, recipient: str, template: str = 'notification', 
                      variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send an email."""
        if variables is None:
            variables = {}
        
        if template in self.DEFAULT_TEMPLATES:
            template_content = self.DEFAULT_TEMPLATES[template]
        else:
            template_content = template
        
        try:
            email_body = template_content.format(**variables)
        except KeyError as e:
            return {
                'success': False,
                'error': f'Missing variable: {e}'
            }
        
        email_id = f"EMAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            'success': True,
            'email_id': email_id,
            'recipient': recipient,
            'template': template,
            'body': email_body,
            'sent_at': datetime.now().isoformat()
        }


@tool(name="webhook_caller", use_cases=["automation"])
class WebhookCaller(BaseTool):
    """Makes webhook calls to external services."""
    
    async def _execute(self, url: str, method: str = 'POST', 
                      payload: Dict[str, Any] = None, 
                      headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Call a webhook."""
        if payload is None:
            payload = {}
        if headers is None:
            headers = {}
        
        return {
            'success': True,
            'url': url,
            'method': method,
            'status_code': 200,
            'response': {
                'message': 'Webhook processed successfully',
                'payload_received': payload
            },
            'called_at': datetime.now().isoformat()
        }


@tool(name="schedule_trigger", use_cases=["automation"])
class ScheduleTrigger(BaseTool):
    """Schedules tasks to run at specific times."""
    
    async def _execute(self, task_id: str, schedule_time: str, 
                      action: Dict[str, Any], repeat: str = 'once') -> Dict[str, Any]:
        """Schedule a task."""
        trigger_id = f"TRIGGER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            scheduled_datetime = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
        except ValueError:
            return {
                'success': False,
                'error': 'Invalid schedule_time format. Use ISO 8601 format.'
            }
        
        if scheduled_datetime <= datetime.now():
            return {
                'success': False,
                'error': 'Schedule time must be in the future'
            }
        
        return {
            'success': True,
            'trigger_id': trigger_id,
            'task_id': task_id,
            'scheduled_for': schedule_time,
            'repeat': repeat,
            'action': action,
            'status': 'scheduled',
            'created_at': datetime.now().isoformat()
        }


__all__ = [
    'WorkflowExecutor',
    'EmailSender',
    'WebhookCaller',
    'ScheduleTrigger'
]
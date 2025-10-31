"""
tests/test_automation_tools.py
Phase 6: Automation Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from agents.tools.automation_tools import (
    WorkflowExecutor,
    EmailSender,
    WebhookCaller,
    ScheduleTrigger
)

User = get_user_model()


class TestWorkflowExecutor(TestCase):
    """Test workflow execution"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        self.executor = WorkflowExecutor(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_workflow_executes_steps(self):
        """Test workflow executes all steps in sequence"""
        workflow_config = {
            'id': 'test_workflow_001',
            'steps': [
                {
                    'type': 'action',
                    'name': 'Log Message',
                    'action': {'type': 'log', 'message': 'Starting workflow'}
                },
                {
                    'type': 'action',
                    'name': 'Send Notification',
                    'action': {'type': 'notify', 'recipient': 'admin'}
                },
                {
                    'type': 'action',
                    'name': 'Final Step',
                    'action': {'type': 'log', 'message': 'Workflow complete'}
                }
            ]
        }
        
        result = await self.executor._execute(workflow_config=workflow_config)
        
        assert result['workflow_id'] == 'test_workflow_001'
        assert result['total_steps'] == 3
        assert result['executed_steps'] == 3
        assert result['success'] is True
        assert len(result['results']) == 3
        
        # Verify each step executed successfully
        for step_result in result['results']:
            assert step_result['status'] == 'completed'
            assert 'timestamp' in step_result
    
    @pytest.mark.asyncio
    async def test_workflow_stops_on_failure(self):
        """Test workflow stops execution when step fails"""
        workflow_config = {
            'id': 'failing_workflow',
            'steps': [
                {
                    'type': 'action',
                    'name': 'Step 1',
                    'action': {'type': 'log', 'message': 'Success'}
                },
                {
                    'type': 'action',
                    'name': 'Bad Step',
                    'action': {'type': 'fail', 'fail': True, 'error': 'Intentional failure'}
                },
                {
                    'type': 'action',
                    'name': 'Step 3',
                    'action': {'type': 'log', 'message': 'Should not reach'}
                }
            ]
        }
        
        result = await self.executor._execute(workflow_config=workflow_config)
        
        assert result['success'] is False
        assert result['executed_steps'] < result['total_steps']
        assert result['status'] == 'failed'
    
    @pytest.mark.asyncio
    async def test_workflow_condition_step(self):
        """Test workflow condition evaluation"""
        workflow_config = {
            'id': 'condition_workflow',
            'steps': [
                {
                    'type': 'condition',
                    'name': 'Check Status',
                    'condition': {
                        'field': 'status',
                        'operator': '==',
                        'value': 'active'
                    }
                },
                {
                    'type': 'action',
                    'name': 'Conditional Action',
                    'action': {'type': 'log', 'message': 'Condition met'}
                }
            ]
        }
        
        result = await self.executor._execute(workflow_config=workflow_config)
        
        assert result['success'] is True
        # Check that condition step has result
        assert 'result' in result['results'][0]
    
    @pytest.mark.asyncio
    async def test_workflow_wait_step(self):
        """Test workflow wait/delay step"""
        workflow_config = {
            'id': 'wait_workflow',
            'steps': [
                {
                    'type': 'wait',
                    'name': 'Delay',
                    'duration': 0.1  # 100ms wait
                },
                {
                    'type': 'action',
                    'name': 'After Wait',
                    'action': {'type': 'log', 'message': 'Waited'}
                }
            ]
        }
        
        result = await self.executor._execute(workflow_config=workflow_config)
        
        assert result['success'] is True
        assert result['results'][0]['result']['waited'] == 0.1


class TestEmailSender(TestCase):
    """Test email sending functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        self.sender = EmailSender(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_email_sends_successfully(self):
        """Test successful email sending with template"""
        result = await self.sender._execute(
            recipient='user@example.com',
            template='notification',
            variables={
                'name': 'John Doe',
                'message': 'Welcome to our platform!'
            }
        )
        
        assert result['success'] is True
        assert result['recipient'] == 'user@example.com'
        assert result['template'] == 'notification'
        assert 'sent_at' in result
        
        # Verify template variables were replaced
        assert 'John Doe' in result['body']
        assert 'Welcome to our platform!' in result['body']
    
    @pytest.mark.asyncio
    async def test_email_reminder_template(self):
        """Test reminder email template"""
        result = await self.sender._execute(
            recipient='attendee@example.com',
            template='reminder',
            variables={
                'name': 'Alice',
                'title': 'Team Meeting'
            }
        )
        
        assert result['success'] is True
        assert 'body' in result
        # The reminder template uses {title} not {name}
        assert 'Team Meeting' in result['body']
        assert result['template'] == 'reminder'
    
    @pytest.mark.asyncio
    async def test_email_notification_template(self):
        """Test notification email template"""
        result = await self.sender._execute(
            recipient='admin@example.com',
            template='notification',
            variables={
                'name': 'Admin',
                'message': 'Server backup completed successfully'
            }
        )
        
        assert result['success'] is True
        assert 'Server backup completed' in result['body']
    
    @pytest.mark.asyncio
    async def test_email_default_template(self):
        """Test email with default notification template"""
        result = await self.sender._execute(
            recipient='test@example.com',
            variables={'name': 'User', 'message': 'Test message'}
        )
        
        assert result['success'] is True
        assert result['template'] == 'notification'


class TestWebhookCaller(TestCase):
    """Test webhook calling functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        self.caller = WebhookCaller(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_webhook_posts_data(self):
        """Test webhook POST request with payload"""
        result = await self.caller._execute(
            url='https://api.example.com/webhook',
            method='POST',
            payload={
                'event': 'user_registered',
                'user_id': '12345',
                'timestamp': '2024-12-01T10:00:00Z'
            },
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': 'test_key_123'
            }
        )
        
        assert result['success'] is True
        assert result['url'] == 'https://api.example.com/webhook'
        assert result['method'] == 'POST'
        assert result['status_code'] == 200
        assert 'called_at' in result
    
    @pytest.mark.asyncio
    async def test_webhook_get_request(self):
        """Test webhook GET request"""
        result = await self.caller._execute(
            url='https://api.example.com/status',
            method='GET'
        )
        
        assert result['success'] is True
        assert result['method'] == 'GET'
        assert result['status_code'] == 200
    
    @pytest.mark.asyncio
    async def test_webhook_with_headers(self):
        """Test webhook call with custom headers"""
        custom_headers = {
            'Authorization': 'Bearer token123',
            'X-Custom-Header': 'custom_value'
        }
        
        result = await self.caller._execute(
            url='https://api.example.com/data',
            method='POST',
            payload={'data': 'test'},
            headers=custom_headers
        )
        
        assert result['success'] is True
        assert 'response' in result
    
    @pytest.mark.asyncio
    async def test_webhook_error_handling(self):
        """Test webhook handles errors gracefully"""
        result = await self.caller._execute(
            url='https://api.example.com/endpoint',
            method='POST',
            payload={'test': 'data'}
        )
        
        # Should complete without raising exceptions
        assert 'success' in result
        assert 'status_code' in result


class TestScheduleTrigger(TestCase):
    """Test schedule trigger integration with workflows"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        self.executor = WorkflowExecutor(agent=self.agent)
        self.trigger = ScheduleTrigger(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_creates(self):
        """Test that schedule trigger can be created"""
        from datetime import datetime, timedelta
        
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        
        result = await self.trigger._execute(
            task_id='daily_backup',
            schedule_time=future_time,
            action={'type': 'workflow', 'workflow_id': 'backup_workflow'},
            repeat='daily'
        )
        
        assert result['success'] is True
        assert result['task_id'] == 'daily_backup'
        assert result['status'] == 'scheduled'
        assert 'trigger_id' in result
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_fires(self):
        """Test that scheduled workflows can be triggered"""
        workflow_config = {
            'id': 'scheduled_backup',
            'trigger': {
                'type': 'schedule',
                'cron': '0 0 * * *',
                'enabled': True
            },
            'steps': [
                {
                    'type': 'action',
                    'name': 'Backup Database',
                    'action': {'type': 'log', 'message': 'Starting backup'}
                },
                {
                    'type': 'action',
                    'name': 'Notify Admin',
                    'action': {'type': 'notify', 'recipient': 'admin@example.com'}
                }
            ]
        }
        
        result = await self.executor._execute(workflow_config=workflow_config)
        
        assert result['success'] is True
        assert result['executed_steps'] == 2
        assert workflow_config['trigger']['type'] == 'schedule'
    
    @pytest.mark.asyncio
    async def test_scheduled_workflow_execution_tracking(self):
        """Test tracking of scheduled workflow executions"""
        workflow_config = {
            'id': 'daily_report',
            'steps': [
                {
                    'type': 'action',
                    'name': 'Generate Report',
                    'action': {'type': 'log', 'message': 'Report generated'}
                }
            ]
        }
        
        # Execute multiple times (simulating scheduled runs)
        results = []
        for i in range(3):
            result = await self.executor._execute(workflow_config=workflow_config)
            results.append(result)
        
        # Verify each execution completed
        assert all(r['success'] for r in results)
        assert all(r['workflow_id'] == 'daily_report' for r in results)
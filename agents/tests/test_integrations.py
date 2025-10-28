"""
Tests for Integration Models and Views - Phase 3
Tests integration CRUD, webhooks, API keys, and LLM setup
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from integrations.models import Integration, WebhookLog, APIKey
from agents.models import Agent
import json

User = get_user_model()


class IntegrationModelTests(TestCase):
    """Test cases for Integration model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
    
    def test_create_openai_integration(self):
        """Test Case 3.1.1: Create OpenAI integration"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-test-key'}
        )
        
        # Assertions
        self.assertEqual(integration.agent, self.agent)
        self.assertEqual(integration.integration_type, 'openai')
        self.assertEqual(integration.config['api_key'], 'sk-test-key')
        self.assertTrue(integration.is_active)
    
    def test_create_anthropic_integration(self):
        """Test Case 3.1.2: Create Anthropic integration"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='Anthropic API',
            integration_type='anthropic',
            config={'api_key': 'sk-ant-test'}
        )
        
        # Assertions
        self.assertEqual(integration.integration_type, 'anthropic')
        self.assertIn('api_key', integration.config)
    
    def test_update_integration_config(self):
        """Test Case 3.1.3: Update integration configuration"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            config={'api_key': 'old-key'}
        )
        
        # Update config
        integration.config['api_key'] = 'new-key'
        integration.config['temperature'] = 0.8
        integration.save()
        
        # Reload and verify
        integration.refresh_from_db()
        self.assertEqual(integration.config['api_key'], 'new-key')
        self.assertEqual(integration.config['temperature'], 0.8)
    
    def test_deactivate_integration(self):
        """Test Case 3.1.4: Deactivate integration"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            is_active=True
        )
        
        # Deactivate
        integration.is_active = False
        integration.save()
        
        # Verify
        self.assertFalse(integration.is_active)
        
        # Check active integrations query
        active = Integration.objects.filter(agent=self.agent, is_active=True)
        self.assertEqual(active.count(), 0)
    
    def test_delete_integration(self):
        """Test Case 3.1.5: Delete integration"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai'
        )
        integration_id = integration.id
        
        # Delete
        integration.delete()
        
        # Verify deletion
        exists = Integration.objects.filter(id=integration_id).exists()
        self.assertFalse(exists)
    
    def test_set_integration_error_status(self):
        """Test Case 3.2.1: Set integration to error status"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai'
        )
        
        # Set error status
        integration.status = Integration.Status.ERROR
        integration.error_message = "API key invalid"
        integration.save()
        
        # Verify
        self.assertEqual(integration.status, Integration.Status.ERROR)
        self.assertEqual(integration.error_message, "API key invalid")
    
    def test_track_last_triggered(self):
        """Test Case 3.2.2: Track last triggered timestamp"""
        from django.utils import timezone
        
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai'
        )
        
        # Update timestamp
        now = timezone.now()
        integration.last_triggered_at = now
        integration.save()
        
        # Verify
        integration.refresh_from_db()
        self.assertIsNotNone(integration.last_triggered_at)


class IntegrationViewTests(TestCase):
    """Test cases for Integration views"""
    
    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_setup_openai_integration(self):
        """Test Case 5.1.1: Setup OpenAI integration via view"""
        url = reverse('agents:agent_setup_llm', kwargs={'pk': self.agent.pk})
        
        data = {
            'provider': 'openai',
            'api_key': 'sk-test-key'
        }
        
        response = self.client.post(url, data)
        
        # Assertions
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # Verify integration created
        integration = Integration.objects.filter(
            agent=self.agent,
            integration_type='openai'
        ).first()
        self.assertIsNotNone(integration)
        self.assertEqual(integration.config['api_key'], 'sk-test-key')
    
    def test_setup_anthropic_integration(self):
        """Test Case 5.1.2: Setup Anthropic integration via view"""
        url = reverse('agents:agent_setup_llm', kwargs={'pk': self.agent.pk})
        
        data = {
            'provider': 'anthropic',
            'api_key': 'sk-ant-test'
        }
        
        response = self.client.post(url, data)
        
        # Assertions
        self.assertEqual(response.status_code, 302)
        
        # Verify integration
        integration = Integration.objects.filter(
            agent=self.agent,
            integration_type='anthropic'
        ).first()
        self.assertIsNotNone(integration)
    
    def test_update_existing_integration(self):
        """Test Case 5.1.3: Update existing integration"""
        # Create existing integration
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            config={'api_key': 'old-key'}
        )
        
        url = reverse('agents:agent_setup_llm', kwargs={'pk': self.agent.pk})
        
        data = {
            'provider': 'openai',
            'api_key': 'new-key'
        }
        
        response = self.client.post(url, data)
        
        # Verify update (not duplicate)
        integrations = Integration.objects.filter(
            agent=self.agent,
            integration_type='openai'
        )
        self.assertEqual(integrations.count(), 1)
        
        # Verify new key
        integration.refresh_from_db()
        self.assertEqual(integration.config['api_key'], 'new-key')
    
    def test_setup_without_api_key(self):
        """Test Case 5.1.4: Setup without API key"""
        url = reverse('agents:agent_setup_llm', kwargs={'pk': self.agent.pk})
        
        data = {
            'provider': 'openai',
            'api_key': ''  # Empty key
        }
        
        response = self.client.post(url, data, follow=True)
        
        # Verify error message
        messages = list(response.context['messages'])
        self.assertTrue(any('required' in str(m).lower() for m in messages))
        
        # Verify no integration created
        integrations = Integration.objects.filter(agent=self.agent)
        self.assertEqual(integrations.count(), 0)
    
    def test_view_llm_setup_page(self):
        """Test Case 5.1.5: View LLM setup page"""
        # Create existing integrations
        Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai'
        )
        
        url = reverse('agents:agent_setup_llm', kwargs={'pk': self.agent.pk})
        response = self.client.get(url)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertIn('agent', response.context)
        self.assertIn('existing_integrations', response.context)
        self.assertEqual(response.context['existing_integrations'].count(), 1)
    
    def test_delete_integration(self):
        """Test Case 5.1.6: Delete integration via view"""
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai'
        )
        
        url = reverse('agents:agent_delete_integration', kwargs={
            'pk': self.agent.pk,
            'integration_id': integration.pk
        })
        
        response = self.client.post(url)
        
        # Assertions
        self.assertEqual(response.status_code, 302)
        
        # Verify deletion
        exists = Integration.objects.filter(pk=integration.pk).exists()
        self.assertFalse(exists)
    
    def test_delete_nonexistent_integration(self):
        """Test Case 5.1.7: Delete non-existent integration"""
        url = reverse('agents:agent_delete_integration', kwargs={
            'pk': self.agent.pk,
            'integration_id': 99999
        })
        
        response = self.client.post(url)
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_access_other_user_integration(self):
        """Test Case 5.1.8: Access other user's integration"""
        # Create another user's agent
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_agent = Agent.objects.create(
            user=other_user,
            name='Other Agent',
            use_case='support'
        )
        
        url = reverse('agents:agent_setup_llm', kwargs={'pk': other_agent.pk})
        response = self.client.get(url)
        
        # Should return 404 (user doesn't own this agent)
        self.assertEqual(response.status_code, 404)


class WebhookLogTests(TestCase):
    """Test cases for Webhook logging"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        self.integration = Integration.objects.create(
            agent=self.agent,
            name='Webhook Integration',
            integration_type='webhook',
            webhook_url='https://example.com/webhook',
            webhook_secret='secret123'
        )
    
    def test_create_webhook_log(self):
        """Test creating webhook log"""
        webhook_log = WebhookLog.objects.create(
            integration=self.integration,
            event_type='message.sent',
            payload={'message': 'Hello'},
            status=WebhookLog.Status.SUCCESS,
            status_code=200
        )
        
        # Assertions
        self.assertEqual(webhook_log.integration, self.integration)
        self.assertEqual(webhook_log.event_type, 'message.sent')
        self.assertEqual(webhook_log.status, WebhookLog.Status.SUCCESS)
    
    def test_webhook_retry_tracking(self):
        """Test webhook retry tracking"""
        webhook_log = WebhookLog.objects.create(
            integration=self.integration,
            event_type='test',
            payload={},
            status=WebhookLog.Status.RETRY,
            retry_count=3
        )
        
        # Assertions
        self.assertEqual(webhook_log.retry_count, 3)
        self.assertEqual(webhook_log.status, WebhookLog.Status.RETRY)


class APIKeyTests(TestCase):
    """Test cases for API Key management"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_api_key(self):
        """Test creating API key"""
        api_key = APIKey.objects.create(
            user=self.user,
            name='Test API Key',
            key='sk-test-123456',
            scopes=['read', 'write']
        )
        
        # Assertions
        self.assertEqual(api_key.user, self.user)
        self.assertEqual(api_key.name, 'Test API Key')
        self.assertIn('read', api_key.scopes)
    
    def test_api_key_usage_tracking(self):
        """Test API key usage tracking"""
        from django.utils import timezone
        
        api_key = APIKey.objects.create(
            user=self.user,
            name='Test Key',
            key='sk-test-123',
            usage_count=0
        )
        
        # Simulate usage
        api_key.usage_count += 1
        api_key.last_used_at = timezone.now()
        api_key.save()
        
        # Verify
        api_key.refresh_from_db()
        self.assertEqual(api_key.usage_count, 1)
        self.assertIsNotNone(api_key.last_used_at)
    
    def test_api_key_deactivation(self):
        """Test API key deactivation"""
        api_key = APIKey.objects.create(
            user=self.user,
            name='Test Key',
            key='sk-test-123',
            is_active=True
        )
        
        # Deactivate
        api_key.is_active = False
        api_key.save()
        
        # Verify
        self.assertFalse(api_key.is_active)


class ToolExecutionTests(TestCase):
    """Test cases for Tool Execution logging"""
    
    def setUp(self):
        """Set up test data"""
        from agents.models import ToolExecution
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
    
    def test_create_tool_execution_record(self):
        """Test Case 6.1.1: Create tool execution record"""
        from agents.models import ToolExecution
        
        tool_exec = ToolExecution.objects.create(
            agent=self.agent,
            tool_name='calculator',
            input_data={'expression': '2+2'},
            output_data='4'
        )
        
        # Assertions
        self.assertEqual(tool_exec.agent, self.agent)
        self.assertEqual(tool_exec.tool_name, 'calculator')
        self.assertEqual(tool_exec.input_data['expression'], '2+2')
        self.assertEqual(tool_exec.output_data, '4')
    
    def test_query_tool_executions(self):
        """Test Case 6.1.2: Query tool executions"""
        from agents.models import ToolExecution
        
        # Create multiple executions
        for i in range(5):
            ToolExecution.objects.create(
                agent=self.agent,
                tool_name='calculator',
                input_data={'expression': f'{i}+{i}'},
                output_data=str(i*2)
            )
        
        # Query
        executions = ToolExecution.objects.filter(agent=self.agent)
        
        # Assertions
        self.assertEqual(executions.count(), 5)
        
        # Verify ordering (most recent first)
        first = executions.first()
        last = executions.last()
        self.assertGreater(first.created_at, last.created_at)
    
    def test_tool_execution_count(self):
        """Test Case 6.1.3: Tool execution count"""
        from agents.models import ToolExecution
        
        # Create executions
        for i in range(10):
            ToolExecution.objects.create(
                agent=self.agent,
                tool_name='calculator',
                input_data={},
                output_data=str(i)
            )
        
        # Count
        count = ToolExecution.objects.filter(agent=self.agent).count()
        
        # Assertions
        self.assertEqual(count, 10)


class IntegrationEndToEndTests(TestCase):
    """End-to-end integration tests"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_complete_openai_workflow(self):
        """Test Case 7.1.1: Complete OpenAI workflow"""
        # Create agent
        agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        
        # Setup OpenAI integration
        url = reverse('agents:agent_setup_llm', kwargs={'pk': agent.pk})
        response = self.client.post(url, {
            'provider': 'openai',
            'api_key': 'sk-test-key'
        })
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify integration created
        integration = Integration.objects.filter(
            agent=agent,
            integration_type='openai'
        ).first()
        self.assertIsNotNone(integration)
        
        # Verify agent detail page shows integration
        detail_url = reverse('agents:agent_detail', kwargs={'pk': agent.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
    
    def test_complete_anthropic_workflow(self):
        """Test Case 7.1.2: Complete Anthropic workflow"""
        # Create agent
        agent = Agent.objects.create(
            user=self.user,
            name='Claude Agent',
            use_case='research'
        )
        
        # Setup Anthropic
        url = reverse('agents:agent_setup_llm', kwargs={'pk': agent.pk})
        response = self.client.post(url, {
            'provider': 'anthropic',
            'api_key': 'sk-ant-test'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify integration
        integration = Integration.objects.filter(
            agent=agent,
            integration_type='anthropic'
        ).first()
        self.assertIsNotNone(integration)
    
    def test_switch_between_agents(self):
        """Test Case 7.1.5: Switch between agents"""
        # Create two agents
        agent1 = Agent.objects.create(
            user=self.user,
            name='Agent 1',
            use_case='support'
        )
        agent2 = Agent.objects.create(
            user=self.user,
            name='Agent 2',
            use_case='research'
        )
        
        # Setup integrations
        Integration.objects.create(
            agent=agent1,
            name='OpenAI 1',
            integration_type='openai',
            config={'api_key': 'key1'}
        )
        Integration.objects.create(
            agent=agent2,
            name='OpenAI 2',
            integration_type='openai',
            config={'api_key': 'key2'}
        )
        
        # Verify each agent has its own integration
        int1 = Integration.objects.get(agent=agent1)
        int2 = Integration.objects.get(agent=agent2)
        
        self.assertNotEqual(int1.config['api_key'], int2.config['api_key'])
        self.assertEqual(int1.agent, agent1)
        self.assertEqual(int2.agent, agent2)
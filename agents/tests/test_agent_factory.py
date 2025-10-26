"""
Tests for Agent Factory - Phase 3
Tests agent creation, LLM integration, and execution
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from agents.models import Agent, ToolExecution
from agents.agents import AgentFactory, ToolRegistry
from integrations.models import Integration
from chat.models import Conversation, Message

User = get_user_model()


class AgentFactoryCreationTests(TestCase):
    """Test cases for agent creation"""
    
    def setUp(self):
        """Set up test user and agent"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support',
            config_json={
                'temperature': 0.7,
                'max_tokens': 1000,
                'tools_enabled': False
            }
        )
    
    def test_create_agent_no_integration(self):
        """Test Case 1.1.3: Create agent without LLM integration"""
        with self.assertRaises(ValueError) as context:
            AgentFactory.create_agent(self.agent)
        
        self.assertIn('No active LLM integration found', str(context.exception))
    
    @patch('agents.agents.ChatOpenAI')
    def test_create_agent_with_openai(self, mock_openai):
        """Test Case 1.1.1: Create agent with OpenAI integration"""
        # Create OpenAI integration
        integration = Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-test-key'}
        )
        
        # Mock OpenAI
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        # Create agent
        agent_dict = AgentFactory.create_agent(self.agent)
        
        # Assertions
        self.assertIn('llm', agent_dict)
        self.assertIn('chain', agent_dict)
        self.assertIn('name', agent_dict)
        self.assertIn('message_history', agent_dict)
        self.assertIn('use_case', agent_dict)
        self.assertIn('agent_model', agent_dict)
        
        # Verify OpenAI was initialized with correct parameters
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        self.assertEqual(call_kwargs['model'], 'gpt-4o-mini')
        self.assertEqual(call_kwargs['api_key'], 'sk-test-key')
        self.assertEqual(call_kwargs['temperature'], 0.7)
        self.assertEqual(call_kwargs['max_tokens'], 1000)
    
    @patch('agents.agents.ChatAnthropic')
    def test_create_agent_with_anthropic(self, mock_anthropic):
        """Test Case 1.1.2: Create agent with Anthropic integration"""
        # Create Anthropic integration
        Integration.objects.create(
            agent=self.agent,
            name='Anthropic API',
            integration_type='anthropic',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-ant-test-key'}
        )
        
        # Mock Anthropic
        mock_llm = Mock()
        mock_anthropic.return_value = mock_llm
        
        # Create agent
        agent_dict = AgentFactory.create_agent(self.agent)
        
        # Assertions
        self.assertIsNotNone(agent_dict)
        
        # Verify Anthropic was initialized
        mock_anthropic.assert_called_once()
        call_kwargs = mock_anthropic.call_args[1]
        self.assertEqual(call_kwargs['model'], 'claude-3-5-sonnet-20241022')
        self.assertEqual(call_kwargs['api_key'], 'sk-ant-test-key')
    
    @patch('agents.agents.ChatOpenAI')
    def test_create_agent_with_tools_enabled(self, mock_openai):
        """Test Case 1.1.4: Create agent with tools enabled"""
        # Update agent config
        self.agent.config_json['tools_enabled'] = True
        self.agent.save()
        
        # Create integration
        Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-test-key'}
        )
        
        # Mock OpenAI
        mock_llm = Mock()
        mock_chain = Mock()
        mock_chain.bind_tools = Mock(return_value=mock_chain)
        mock_openai.return_value = mock_llm
        
        with patch('agents.agents.RunnablePassthrough', return_value=mock_chain):
            with patch('agents.agents.ChatPromptTemplate.from_messages') as mock_prompt:
                mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)
                
                # Create agent
                agent_dict = AgentFactory.create_agent(self.agent)
                
                # Assertions
                self.assertIn('tools', agent_dict)
                self.assertIsInstance(agent_dict['tools'], list)
    
    @patch('agents.agents.ChatOpenAI')
    def test_create_agent_with_custom_prompt(self, mock_openai):
        """Test Case 1.1.5: Create agent with custom prompt template"""
        # Set custom prompt
        self.agent.prompt_template = "You are {agent_name}, a helpful {use_case} assistant."
        self.agent.save()
        
        # Create integration
        Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-test-key'}
        )
        
        # Mock OpenAI
        mock_openai.return_value = Mock()
        
        # Create agent
        agent_dict = AgentFactory.create_agent(self.agent)
        
        # Verify custom prompt is used
        self.assertIsNotNone(agent_dict)
    
    @patch('agents.agents.ChatOpenAI')
    def test_create_agent_with_conversation_history(self, mock_openai):
        """Test Case 1.1.6: Create agent with conversation history"""
        # Create integration
        Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-test-key'}
        )
        
        # Create conversation with messages
        conversation = Conversation.objects.create(
            agent=self.agent,
            is_active=True
        )
        
        # Add messages
        Message.objects.create(
            conversation=conversation,
            role='user',
            content='Hello'
        )
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Hi there!'
        )
        
        # Mock OpenAI
        mock_openai.return_value = Mock()
        
        # Create agent
        agent_dict = AgentFactory.create_agent(self.agent)
        
        # Verify history loaded
        message_history = agent_dict['message_history']
        self.assertEqual(len(message_history.messages), 2)
    
    @patch('agents.agents.ChatOpenAI')
    @patch('agents.agents.ChatAnthropic')
    def test_fallback_to_alternate_llm(self, mock_anthropic, mock_openai):
        """Test Case 1.1.7: Fallback to alternate LLM on failure"""
        # Create both integrations
        Integration.objects.create(
            agent=self.agent,
            name='OpenAI API',
            integration_type='openai',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'invalid-key'}
        )
        Integration.objects.create(
            agent=self.agent,
            name='Anthropic API',
            integration_type='anthropic',
            status=Integration.Status.ACTIVE,
            is_active=True,
            config={'api_key': 'sk-ant-test'}
        )
        
        # Make OpenAI fail
        mock_openai.side_effect = Exception("API Error")
        
        # Mock Anthropic to succeed
        mock_anthropic.return_value = Mock()
        
        # Create agent - should fallback to Anthropic
        agent_dict = AgentFactory.create_agent(self.agent)
        
        # Verify fallback occurred
        self.assertIsNotNone(agent_dict)
        mock_anthropic.assert_called()


class AgentFactoryExecutionTests(TestCase):
    """Test cases for agent execution"""
    
    def setUp(self):
        """Set up test agent with mock LLM"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support',
            config_json={'temperature': 0.7, 'max_tokens': 1000}
        )
        
        # Create mock agent dict
        self.mock_llm = Mock()
        self.mock_chain = Mock()
        self.message_history = MagicMock()
        self.message_history.messages = []
        self.message_history.add_user_message = Mock()
        self.message_history.add_ai_message = Mock()
        
        self.agent = {
            'llm': self.mock_llm,
            'chain': self.mock_chain,
            'name': 'Test Agent',
            'message_history': self.message_history,
            'use_case': 'support',
            'agent_model': self.agent_model
        }
    
    def test_execute_simple_query(self):
        """Test Case 1.2.1: Execute simple query"""
        # Mock response
        mock_response = Mock()
        mock_response.content = "The answer is 4"
        self.mock_chain.invoke.return_value = mock_response
        
        # Execute
        response = AgentFactory.execute_agent(self.agent, "What is 2 + 2?")
        
        # Assertions
        self.assertEqual(response, "The answer is 4")
        self.message_history.add_user_message.assert_called_once_with("What is 2 + 2?")
        self.message_history.add_ai_message.assert_called_once_with("The answer is 4")
    
    def test_execute_with_tool_usage(self):
        """Test Case 1.2.2: Execute with tool usage (calculator)"""
        # Add tools to agent
        self.agent['tools'] = ToolRegistry.get_tools()
        
        # Mock response with tool call
        mock_response = Mock()
        mock_response.content = "Calculating..."
        mock_response.tool_calls = [
            {
                'name': 'calculator',
                'args': {'expression': '15 * 23 + 100'}
            }
        ]
        self.mock_chain.invoke.return_value = mock_response
        
        # Execute
        with patch('agents.agents.ToolRegistry.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.run.return_value = "445"
            mock_get_tool.return_value = mock_tool
            
            response = AgentFactory.execute_agent(self.agent, "Calculate 15 * 23 + 100")
        
        # Assertions
        self.assertIn("445", response)
        
        # Verify ToolExecution was logged
        tool_execution = ToolExecution.objects.filter(
            agent=self.agent_model,
            tool_name='calculator'
        ).first()
        self.assertIsNotNone(tool_execution)
    
    def test_execute_multi_turn_conversation(self):
        """Test Case 1.2.3: Execute multi-turn conversation"""
        # First message
        mock_response1 = Mock()
        mock_response1.content = "Nice to meet you, Alice!"
        self.mock_chain.invoke.return_value = mock_response1
        
        response1 = AgentFactory.execute_agent(self.agent, "My name is Alice")
        
        # Simulate history update
        self.message_history.messages = [
            Mock(role='user', content='My name is Alice'),
            Mock(role='assistant', content='Nice to meet you, Alice!')
        ]
        
        # Second message
        mock_response2 = Mock()
        mock_response2.content = "Your name is Alice!"
        self.mock_chain.invoke.return_value = mock_response2
        
        response2 = AgentFactory.execute_agent(self.agent, "What's my name?")
        
        # Assertions
        self.assertEqual(response1, "Nice to meet you, Alice!")
        self.assertEqual(response2, "Your name is Alice!")
        self.assertEqual(self.message_history.add_user_message.call_count, 2)
    
    def test_execute_with_error_handling(self):
        """Test Case 1.2.4: Execute with error handling"""
        # Mock chain to raise exception
        self.mock_chain.invoke.side_effect = Exception("LLM Error")
        
        # Execute and expect exception
        with self.assertRaises(Exception) as context:
            AgentFactory.execute_agent(self.agent, "Test input")
        
        self.assertIn("LLM Error", str(context.exception))
    
    def test_execute_with_long_input(self):
        """Test Case 1.2.5: Execute with long input"""
        # Create long input
        long_input = "A" * 5000
        
        # Mock response
        mock_response = Mock()
        mock_response.content = "Processed long input"
        self.mock_chain.invoke.return_value = mock_response
        
        # Execute
        response = AgentFactory.execute_agent(self.agent, long_input)
        
        # Assertions
        self.assertEqual(response, "Processed long input")
        self.mock_chain.invoke.assert_called_once()


class ToolRegistryTests(TestCase):
    """Test cases for Tool Registry"""
    
    def test_register_calculator_tool(self):
        """Test Case 2.1.1: Register calculator tool"""
        from agents.agents import calculator
        
        # Verify tool is registered
        tool = ToolRegistry.get_tool('calculator')
        self.assertIsNotNone(tool)
        self.assertEqual(tool, calculator)
    
    def test_get_all_tools(self):
        """Test Case 2.1.2: Get all registered tools"""
        tools = ToolRegistry.get_tools()
        
        # Assertions
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
    
    def test_get_nonexistent_tool(self):
        """Test Case 2.1.3: Get non-existent tool"""
        tool = ToolRegistry.get_tool('nonexistent_tool')
        
        # Assertions
        self.assertIsNone(tool)
    
    def test_calculator_valid_expression(self):
        """Test Case 2.2.1: Execute calculator with valid expression"""
        from agents.agents import calculator
        
        test_cases = [
            ("2 + 2", "4"),
            ("10 * 5", "50"),
            ("100 / 4", "25.0"),
            ("sum([1, 2, 3, 4, 5])", "15")
        ]
        
        for expression, expected in test_cases:
            result = calculator(expression)
            self.assertEqual(result, expected)
    
    def test_calculator_invalid_expression(self):
        """Test Case 2.2.2: Execute calculator with invalid expression"""
        from agents.agents import calculator
        
        result = calculator("invalid expression")
        
        # Assertions
        self.assertIn("Error", result)
    
    def test_calculator_security(self):
        """Test Case 2.2.3: Calculator security test"""
        from agents.agents import calculator
        
        # Attempt malicious code
        malicious_expressions = [
            "__import__('os').system('ls')",
            "open('/etc/passwd').read()",
            "exec('import os; os.system(\"ls\")')"
        ]
        
        for expr in malicious_expressions:
            result = calculator(expr)
            # Should return error, not execute
            self.assertIn("Error", result)


class AgentModelTests(TestCase):
    """Test cases for Agent model methods"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support',
            is_active=True
        )
    
    def test_get_default_config(self):
        """Test Case 4.1.1: Get default configuration"""
        config = self.agent.get_default_config()
        
        # Assertions
        self.assertEqual(config['provider'], 'openai')
        self.assertEqual(config['model'], 'gpt-4o-mini')
        self.assertEqual(config['temperature'], 0.7)
        self.assertEqual(config['max_tokens'], 1000)
        self.assertTrue(config['tools_enabled'])
    
    def test_override_default_config(self):
        """Test Case 4.1.2: Override default configuration"""
        self.agent.config_json = {
            'temperature': 0.5,
            'custom_field': 'custom_value'
        }
        self.agent.save()
        
        config = self.agent.get_default_config()
        
        # Assertions
        self.assertEqual(config['temperature'], 0.5)
        self.assertEqual(config['custom_field'], 'custom_value')
        self.assertEqual(config['model'], 'gpt-4o-mini')  # Default preserved
    
    def test_get_conversation_count(self):
        """Test Case 4.1.3: Get conversation count"""
        # Create conversations
        for i in range(5):
            Conversation.objects.create(agent=self.agent)
        
        count = self.agent.get_conversation_count()
        
        # Assertions
        self.assertEqual(count, 5)
    
    def test_user_can_chat_owner(self):
        """Test Case 4.2.1: Owner can chat"""
        can_chat = self.agent.can_user_chat(self.user)
        
        # Assertions
        self.assertTrue(can_chat)
    
    def test_user_can_chat_non_owner(self):
        """Test Case 4.2.2: Non-owner cannot chat"""
        can_chat = self.agent.can_user_chat(self.other_user)
        
        # Assertions
        self.assertFalse(can_chat)
    
    def test_user_can_chat_inactive_agent(self):
        """Test Case 4.2.3: Cannot chat with inactive agent"""
        self.agent.is_active = False
        self.agent.save()
        
        can_chat = self.agent.can_user_chat(self.user)
        
        # Assertions
        self.assertFalse(can_chat)
    
    def test_user_can_embed(self):
        """Test Case 4.2.4: User can embed active agent"""
        can_embed = self.agent.can_user_embed()
        
        # Assertions
        self.assertTrue(can_embed)
    
    def test_user_cannot_embed_inactive(self):
        """Test Case 4.2.4: Cannot embed inactive agent"""
        self.agent.is_active = False
        self.agent.save()
        
        can_embed = self.agent.can_user_embed()
        
        # Assertions
        self.assertFalse(can_embed)
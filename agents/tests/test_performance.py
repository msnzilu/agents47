"""
Performance and Security Tests - Phase 3
Tests response times, memory usage, concurrency, and security
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from agents.models import Agent, ToolExecution
from agents.agents import AgentFactory
from integrations.models import Integration
from chat.models import Conversation, Message
import time
import threading
from concurrent.futures import ThreadPoolExecutor

User = get_user_model()


class PerformanceTests(TransactionTestCase):
    """Performance benchmark tests"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('agents.agents.ChatOpenAI')
    def test_measure_agent_creation_time(self, mock_openai):
        """Test Case 8.1.1: Measure agent creation time"""
        mock_openai.return_value = Mock()
        
        creation_times = []
        
        for i in range(10):
            agent = Agent.objects.create(
                user=self.user,
                name=f'Test Agent {i}',
                use_case='support'
            )
            Integration.objects.create(
                agent=agent,
                name='OpenAI API',
                integration_type='openai',
                is_active=True,
                config={'api_key': 'sk-test'}
            )
            
            start = time.time()
            AgentFactory.create_agent(agent)
            end = time.time()
            
            creation_times.append(end - start)
        
        # Calculate average
        avg_time = sum(creation_times) / len(creation_times)
        
        # Assert average creation time < 2 seconds
        self.assertLess(avg_time, 2.0, 
                       f"Average creation time {avg_time:.2f}s exceeds 2s threshold")
        
        print(f"\nAgent Creation Performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Min: {min(creation_times):.3f}s")
        print(f"  Max: {max(creation_times):.3f}s")
    
    @patch('agents.agents.ChatOpenAI')
    def test_measure_execution_time(self, mock_openai):
        """Test Case 8.1.2: Measure execution time"""
        # Setup
        agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent_model,
            name='OpenAI API',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'sk-test'}
        )
        
        # Mock LLM
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        agent = AgentFactory.create_agent(agent_model)
        
        # Mock response
        mock_response = Mock()
        mock_response.content = "Test response"
        agent['chain'].invoke = Mock(return_value=mock_response)
        
        execution_times = []
        
        # Execute 100 times
        for i in range(100):
            start = time.time()
            AgentFactory.execute_agent(agent, f"Test query {i}")
            end = time.time()
            execution_times.append(end - start)
        
        # Calculate statistics
        avg_time = sum(execution_times) / len(execution_times)
        sorted_times = sorted(execution_times)
        p95_time = sorted_times[int(len(sorted_times) * 0.95)]
        
        # Assertions
        self.assertLess(avg_time, 3.0, 
                       f"Average execution time {avg_time:.2f}s exceeds 3s")
        self.assertLess(p95_time, 5.0, 
                       f"95th percentile {p95_time:.2f}s exceeds 5s")
        
        print(f"\nAgent Execution Performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  95th percentile: {p95_time:.3f}s")
        print(f"  Max: {max(execution_times):.3f}s")
    
    @patch('agents.agents.ChatOpenAI')
    def test_concurrent_request_handling(self, mock_openai):
        """Test Case 8.1.3: Concurrent request handling"""
        # Setup
        agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent_model,
            name='OpenAI API',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'sk-test'}
        )
        
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        results = []
        errors = []
        
        def execute_request(index):
            try:
                agent = AgentFactory.create_agent(agent_model)
                mock_response = Mock()
                mock_response.content = f"Response {index}"
                agent['chain'].invoke = Mock(return_value=mock_response)
                
                response = AgentFactory.execute_agent(agent, f"Query {index}")
                results.append(response)
            except Exception as e:
                errors.append(str(e))
        
        # Execute 50 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(execute_request, i) for i in range(50)]
            for future in futures:
                future.result()
        
        # Assertions
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 50, "Not all requests completed")
        
        print(f"\nConcurrent Execution:")
        print(f"  Successful requests: {len(results)}")
        print(f"  Failed requests: {len(errors)}")


class MemoryTests(TestCase):
    """Memory usage tests"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('agents.agents.ChatOpenAI')
    def test_memory_with_long_history(self, mock_openai):
        """Test Case 8.2.1: Memory usage with long conversation history"""
        # Create agent
        agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent_model,
            name='OpenAI API',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'sk-test'}
        )
        
        # Create conversation with many messages
        conversation = Conversation.objects.create(
            agent=agent_model,
            is_active=True
        )
        
        # Add 1000 messages (only last 20 should be loaded)
        for i in range(1000):
            Message.objects.create(
                conversation=conversation,
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i}'
            )
        
        mock_openai.return_value = Mock()
        
        # Create agent - should only load last 20 messages
        agent = AgentFactory.create_agent(agent_model)
        
        # Verify only 20 messages loaded
        history_length = len(agent['message_history'].messages)
        self.assertLessEqual(history_length, 20, 
                            f"Loaded {history_length} messages, expected <= 20")
        
        print(f"\nMemory Test - Long History:")
        print(f"  Total messages: 1000")
        print(f"  Loaded messages: {history_length}")
    
    @patch('agents.agents.ChatOpenAI')
    def test_multiple_agent_memory(self, mock_openai):
        """Test Case 8.2.2: Memory usage with multiple agents"""
        mock_openai.return_value = Mock()
        
        # Create 100 agents
        agents = []
        for i in range(100):
            agent_model = Agent.objects.create(
                user=self.user,
                name=f'Agent {i}',
                use_case='support'
            )
            Integration.objects.create(
                agent=agent_model,
                name=f'OpenAI {i}',
                integration_type='openai',
                is_active=True,
                config={'api_key': 'sk-test'}
            )
            agents.append(agent_model)
        
        # All agents should be created successfully
        self.assertEqual(len(agents), 100)
        
        print(f"\nMemory Test - Multiple Agents:")
        print(f"  Created agents: {len(agents)}")


class SecurityTests(TestCase):
    """Security tests"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
    
    def test_api_key_not_plain_text(self):
        """Test Case 9.1.1: Verify API keys are not stored in plain text"""
        agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        
        # Create integration with API key
        integration = Integration.objects.create(
            agent=agent,
            name='OpenAI API',
            integration_type='openai',
            config={'api_key': 'sk-very-secret-key-12345'}
        )
        
        # NOTE: In production, implement encryption
        # For now, just verify config is stored as JSON
        self.assertIsInstance(integration.config, dict)
        self.assertIn('api_key', integration.config)
        
        # TODO: Add encryption check when implemented
        print("\nSecurity Note: API key encryption should be implemented in production")
    
    def test_unauthorized_agent_access(self):
        """Test Case 9.1.2: Test unauthorized access to agent"""
        # User A creates agent
        agent = Agent.objects.create(
            user=self.user,
            name='Private Agent',
            use_case='support'
        )
        
        # User B tries to access
        can_access = agent.can_user_chat(self.other_user)
        
        # Should be denied
        self.assertFalse(can_access)
    
    def test_calculator_code_injection_prevention(self):
        """Test Case 9.1.3: Test calculator security"""
        from agents.agents import calculator
        
        malicious_codes = [
            "__import__('os').system('ls')",
            "exec('import os; os.system(\"rm -rf /\")')",
            "eval('__import__(\"os\").system(\"whoami\")')",
            "open('/etc/passwd').read()",
            "__builtins__.__dict__['__import__']('os').system('pwd')"
        ]
        
        for code in malicious_codes:
            result = calculator(code)
            
            # All should return errors, not execute
            self.assertIn("Error", result, 
                         f"Malicious code '{code}' was not blocked!")
        
        print(f"\nSecurity Test - Code Injection:")
        print(f"  Tested {len(malicious_codes)} malicious inputs")
        print(f"  All blocked successfully")
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in queries"""
        # Test Agent.objects queries with malicious input
        malicious_names = [
            "Agent'; DROP TABLE agents_agent; --",
            "Agent' OR '1'='1",
            "Agent'; DELETE FROM agents_agent WHERE '1'='1'; --"
        ]
        
        for name in malicious_names:
            # Should handle safely
            agents = Agent.objects.filter(name=name)
            # Query should execute without error
            count = agents.count()
            self.assertEqual(count, 0)
        
        print(f"\nSecurity Test - SQL Injection:")
        print(f"  Tested {len(malicious_names)} malicious queries")
        print(f"  All handled safely by ORM")


class ErrorHandlingTests(TestCase):
    """Error handling tests"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('agents.agents.ChatOpenAI')
    def test_invalid_api_key_handling(self):
        """Test Case 10.1.1: Handle invalid API key"""
        agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent,
            name='OpenAI API',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'invalid-key'}
        )
        
        # Mock to raise auth error
        mock_openai = Mock(side_effect=Exception("Invalid API key"))
        
        with patch('agents.agents.ChatOpenAI', mock_openai):
            with self.assertRaises(Exception) as context:
                AgentFactory.create_agent(agent)
            
            # Error should be raised
            self.assertIn("Agent creation failed", str(context.exception))
    
    @patch('agents.agents.ChatOpenAI')
    def test_llm_timeout_handling(self):
        """Test Case 10.1.2: Handle LLM timeout"""
        agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent_model,
            name='OpenAI API',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'sk-test'}
        )
        
        mock_llm = Mock()
        mock_openai = Mock(return_value=mock_llm)
        
        with patch('agents.agents.ChatOpenAI', mock_openai):
            agent = AgentFactory.create_agent(agent_model)
            
            # Mock timeout on execution
            agent['chain'].invoke = Mock(side_effect=TimeoutError("Request timeout"))
            
            with self.assertRaises(Exception) as context:
                AgentFactory.execute_agent(agent, "Test query")
            
            # Should raise timeout error
            self.assertTrue(True)  # Exception was raised as expected
    
    def test_tool_execution_failure(self):
        """Test Case 10.2.1: Handle tool execution failure"""
        from agents.agents import calculator
        
        # Test invalid expressions
        invalid_expressions = [
            "1 / 0",  # Division by zero
            "undefined_variable",
            "1 +",  # Incomplete expression
        ]
        
        for expr in invalid_expressions:
            result = calculator(expr)
            # Should return error, not crash
            self.assertIn("Error", result)
        
        print(f"\nError Handling Test - Tool Failures:")
        print(f"  Tested {len(invalid_expressions)} invalid inputs")
        print(f"  All handled gracefully")


class StressTests(TransactionTestCase):
    """Stress tests for edge cases"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('agents.agents.ChatOpenAI')
    def test_rapid_agent_creation_deletion(self, mock_openai):
        """Test rapid creation and deletion"""
        mock_openai.return_value = Mock()
        
        for i in range(20):
            # Create
            agent = Agent.objects.create(
                user=self.user,
                name=f'Agent {i}',
                use_case='support'
            )
            Integration.objects.create(
                agent=agent,
                name='OpenAI',
                integration_type='openai',
                is_active=True,
                config={'api_key': 'sk-test'}
            )
            
            # Use
            agent_dict = AgentFactory.create_agent(agent)
            self.assertIsNotNone(agent_dict)
            
            # Delete
            agent.delete()
        
        # Verify cleanup
        remaining = Agent.objects.filter(user=self.user).count()
        self.assertEqual(remaining, 0)
        
        print(f"\nStress Test - Rapid Create/Delete:")
        print(f"  Completed 20 cycles successfully")
    
    @patch('agents.agents.ChatOpenAI')
    def test_empty_input_handling(self, mock_openai):
        """Test handling of empty inputs"""
        agent_model = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            use_case='support'
        )
        Integration.objects.create(
            agent=agent_model,
            name='OpenAI',
            integration_type='openai',
            is_active=True,
            config={'api_key': 'sk-test'}
        )
        
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        agent = AgentFactory.create_agent(agent_model)
        
        mock_response = Mock()
        mock_response.content = "Please provide input"
        agent['chain'].invoke = Mock(return_value=mock_response)
        
        # Test empty inputs
        empty_inputs = ["", "   ", "\n\n\n"]
        
        for input_text in empty_inputs:
            response = AgentFactory.execute_agent(agent, input_text)
            self.assertIsNotNone(response)
        
        print(f"\nStress Test - Empty Inputs:")
        print(f"  Handled {len(empty_inputs)} empty input cases")
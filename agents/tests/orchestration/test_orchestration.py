"""
agents/tests/test_orchestration.py
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent, AgentOrchestration, OrchestrationExecution
from agents.services.orchestration import OrchestrationEngine

User = get_user_model()


@pytest.mark.django_db
class TestAgentOrchestration(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        
        # Create test agents
        self.orchestrator = Agent.objects.create(
            user=self.user,
            name='Orchestrator',
            use_case='research'
        )
        
        self.research_agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        
        self.support_agent = Agent.objects.create(
            user=self.user,
            name='Support Agent',
            use_case='support'
        )
    
    def test_create_sequential_orchestration(self):
        """Test creating sequential orchestration"""
        orchestration = AgentOrchestration.objects.create(
            name='Sequential Test',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            strategy=AgentOrchestration.OrchestrationStrategy.SEQUENTIAL,
            workflow_config={
                'steps': [
                    {'agent_id': self.research_agent.id, 'execution_order': 1},
                    {'agent_id': self.support_agent.id, 'execution_order': 2}
                ],
                'synthesis_strategy': 'concatenate'
            }
        )
        
        orchestration.participant_agents.add(self.research_agent, self.support_agent)
        
        self.assertEqual(orchestration.strategy, 'sequential')
        self.assertEqual(orchestration.participant_agents.count(), 2)
    
    def test_validate_workflow_no_errors(self):
        """Test workflow validation passes for valid config"""
        orchestration = AgentOrchestration.objects.create(
            name='Valid Workflow',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            workflow_config={
                'steps': [
                    {'agent_id': self.research_agent.id},
                    {'agent_id': self.support_agent.id}
                ]
            }
        )
        
        orchestration.participant_agents.add(self.research_agent, self.support_agent)
        
        errors = orchestration.validate_workflow()
        self.assertEqual(len(errors), 0)
    
    def test_validate_workflow_invalid_agent(self):
        """Test workflow validation fails for invalid agent"""
        orchestration = AgentOrchestration.objects.create(
            name='Invalid Workflow',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            workflow_config={
                'steps': [
                    {'agent_id': 99999}  # Non-existent agent
                ]
            }
        )
        
        errors = orchestration.validate_workflow()
        self.assertGreater(len(errors), 0)
        self.assertIn('Invalid agent references', errors[0])
    
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Test sequential orchestration execution"""
        orchestration = AgentOrchestration.objects.create(
            name='Sequential Exec',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            strategy=AgentOrchestration.OrchestrationStrategy.SEQUENTIAL,
            workflow_config={
                'steps': [
                    {'agent_id': self.research_agent.id, 'execution_order': 1},
                    {'agent_id': self.support_agent.id, 'execution_order': 2}
                ]
            }
        )
        
        orchestration.participant_agents.add(self.research_agent, self.support_agent)
        
        engine = OrchestrationEngine(orchestration)
        result = await engine.execute("Test query")
        
        self.assertIn('response', result)
        self.assertIn('agent_outputs', result)
        self.assertEqual(len(result['agent_outputs']), 2)
    
    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test parallel orchestration execution"""
        orchestration = AgentOrchestration.objects.create(
            name='Parallel Exec',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            strategy=AgentOrchestration.OrchestrationStrategy.PARALLEL,
            workflow_config={
                'steps': [
                    {'agent_id': self.research_agent.id},
                    {'agent_id': self.support_agent.id}
                ],
                'max_parallel_agents': 2
            }
        )
        
        orchestration.participant_agents.add(self.research_agent, self.support_agent)
        
        engine = OrchestrationEngine(orchestration)
        result = await engine.execute("Test query")
        
        self.assertTrue(result.get('parallel_execution'))
        self.assertEqual(len(result['agent_outputs']), 2)
    
    def test_orchestration_statistics(self):
        """Test orchestration statistics tracking"""
        orchestration = AgentOrchestration.objects.create(
            name='Stats Test',
            user=self.user,
            orchestrator_agent=self.orchestrator,
            total_executions=10,
            successful_executions=8,
            average_execution_time_ms=1500
        )
        
        self.assertEqual(orchestration.total_executions, 10)
        self.assertEqual(orchestration.successful_executions, 8)
        self.assertEqual(orchestration.average_execution_time_ms, 1500)
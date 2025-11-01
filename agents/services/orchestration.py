"""
agents/services/orchestration.py
"""

from typing import Dict, List, Any, Optional
from django.db import transaction
from celery import group, chain, chord
import logging
from datetime import datetime
from agents.models import (
    AgentOrchestration,
    OrchestrationExecution,
    AgentCommunication,
    Agent
)

logger = logging.getLogger(__name__)


class OrchestrationService:
    """
    Engine for executing multi-agent orchestrations
    """
    
    def __init__(self, orchestration: AgentOrchestration):
        self.orchestration = orchestration
        self.execution = None
    
    async def execute(self, user_query: str, conversation=None) -> Dict[str, Any]:
        """
        Execute the orchestration workflow
        
        Args:
            user_query: User's input query
            conversation: Optional conversation context
            
        Returns:
            Dictionary with final response and metadata
        """
        # Create execution record
        self.execution = OrchestrationExecution.objects.create(
            orchestration=self.orchestration,
            conversation=conversation,
            user_query=user_query,
            status=OrchestrationExecution.Status.RUNNING,
            started_at=datetime.now()
        )
        
        try:
            # Route based on strategy
            if self.orchestration.strategy == AgentOrchestration.OrchestrationStrategy.SEQUENTIAL:
                result = await self._execute_sequential(user_query)
            
            elif self.orchestration.strategy == AgentOrchestration.OrchestrationStrategy.PARALLEL:
                result = await self._execute_parallel(user_query)
            
            elif self.orchestration.strategy == AgentOrchestration.OrchestrationStrategy.CONDITIONAL:
                result = await self._execute_conditional(user_query)
            
            elif self.orchestration.strategy == AgentOrchestration.OrchestrationStrategy.HIERARCHICAL:
                result = await self._execute_hierarchical(user_query)
            
            else:
                raise ValueError(f"Unknown strategy: {self.orchestration.strategy}")
            
            # Mark as completed
            execution_time = (datetime.now() - self.execution.started_at).total_seconds() * 1000
            
            self.execution.status = OrchestrationExecution.Status.COMPLETED
            self.execution.final_response = result['response']
            self.execution.agent_outputs = result['agent_outputs']
            self.execution.completed_at = datetime.now()
            self.execution.execution_time_ms = int(execution_time)
            self.execution.save()
            
            # Update orchestration stats
            self.orchestration.total_executions += 1
            self.orchestration.successful_executions += 1
            self._update_average_execution_time(execution_time)
            self.orchestration.save()
            
            return result
        
        except Exception as e:
            logger.error(f"Orchestration execution failed: {e}")
            
            self.execution.status = OrchestrationExecution.Status.FAILED
            self.execution.error_message = str(e)
            self.execution.completed_at = datetime.now()
            self.execution.save()
            
            self.orchestration.total_executions += 1
            self.orchestration.save()
            
            raise
    
    async def _execute_sequential(self, query: str) -> Dict[str, Any]:
        """Execute agents sequentially"""
        agent_outputs = {}
        current_input = query
        
        steps = self.orchestration.workflow_config.get('steps', [])
        
        for step in sorted(steps, key=lambda x: x.get('execution_order', 0)):
            agent_id = step['agent_id']
            agent = Agent.objects.get(id=agent_id)
            
            # Execute agent
            output = await self._execute_agent(agent, current_input, agent_outputs)
            agent_outputs[str(agent_id)] = output
            
            # Use output as input for next agent
            current_input = output['response']
            
            # Log communication
            if len(agent_outputs) > 1:
                prev_agent_id = steps[len(agent_outputs) - 2]['agent_id']
                self._log_communication(prev_agent_id, agent_id, current_input)
        
        # Synthesize final response
        final_response = await self._synthesize_responses(agent_outputs)
        
        return {
            'response': final_response,
            'agent_outputs': agent_outputs,
            'execution_order': [step['agent_id'] for step in steps]
        }
    
    async def _execute_parallel(self, query: str) -> Dict[str, Any]:
        """Execute agents in parallel"""
        from asgiref.sync import sync_to_async
        import asyncio
        
        steps = self.orchestration.workflow_config.get('steps', [])
        max_parallel = self.orchestration.workflow_config.get('max_parallel_agents', 3)
        
        # Create tasks for parallel execution
        tasks = []
        for step in steps:
            agent_id = step['agent_id']
            agent = await sync_to_async(Agent.objects.get)(id=agent_id)
            tasks.append(self._execute_agent(agent, query, {}))
        
        # Execute in batches to respect max_parallel
        agent_outputs = {}
        for i in range(0, len(tasks), max_parallel):
            batch = tasks[i:i + max_parallel]
            results = await asyncio.gather(*batch)
            
            for j, result in enumerate(results):
                agent_id = steps[i + j]['agent_id']
                agent_outputs[str(agent_id)] = result
        
        # Synthesize final response
        final_response = await self._synthesize_responses(agent_outputs)
        
        return {
            'response': final_response,
            'agent_outputs': agent_outputs,
            'parallel_execution': True
        }
    
    async def _execute_conditional(self, query: str) -> Dict[str, Any]:
        """Execute agents based on conditions"""
        from agents.execution import AgentFactory
        
        agent_outputs = {}
        
        # First, execute orchestrator to determine routing
        orchestrator = self.orchestration.orchestrator_agent
        orchestrator_instance = AgentFactory.create_agent(orchestrator)
        
        routing_result = await AgentFactory.execute_agent_async(
            orchestrator_instance,
            f"Analyze this query and determine which agents to route to: {query}"
        )
        
        # Parse routing decision (simplified - in production, use structured output)
        steps = self.orchestration.workflow_config.get('steps', [])
        
        for step in steps:
            condition = step.get('condition', 'always')
            
            should_execute = False
            if condition == 'always':
                should_execute = True
            elif condition == 'if_needed':
                # Check if orchestrator recommended this agent
                agent_name = Agent.objects.get(id=step['agent_id']).name
                should_execute = agent_name.lower() in routing_result['response'].lower()
            
            if should_execute:
                agent_id = step['agent_id']
                agent = Agent.objects.get(id=agent_id)
                output = await self._execute_agent(agent, query, agent_outputs)
                agent_outputs[str(agent_id)] = output
        
        # Synthesize final response
        final_response = await self._synthesize_responses(agent_outputs)
        
        return {
            'response': final_response,
            'agent_outputs': agent_outputs,
            'routing_decision': routing_result['response']
        }
    
    async def _execute_hierarchical(self, query: str) -> Dict[str, Any]:
        """Execute agents in hierarchical structure"""
        # Orchestrator breaks down task, assigns to subordinates, synthesizes
        from agents.execution import AgentFactory
        
        orchestrator = self.orchestration.orchestrator_agent
        orchestrator_instance = AgentFactory.create_agent(orchestrator)
        
        # Step 1: Orchestrator plans subtasks
        planning_result = await AgentFactory.execute_agent_async(
            orchestrator_instance,
            f"Break down this task into subtasks: {query}"
        )
        
        # Step 2: Execute subordinate agents (simplified)
        agent_outputs = {}
        steps = self.orchestration.workflow_config.get('steps', [])
        
        for step in steps:
            agent_id = step['agent_id']
            agent = Agent.objects.get(id=agent_id)
            
            # Create subtask for this agent (in production, parse from planning_result)
            subtask = f"Handle your part of: {query}"
            output = await self._execute_agent(agent, subtask, agent_outputs)
            agent_outputs[str(agent_id)] = output
        
        # Step 3: Orchestrator synthesizes results
        synthesis_prompt = f"""
        Original query: {query}
        
        Subordinate agent results:
        {self._format_agent_outputs(agent_outputs)}
        
        Synthesize a final response:
        """
        
        final_result = await AgentFactory.execute_agent_async(
            orchestrator_instance,
            synthesis_prompt
        )
        
        return {
            'response': final_result['response'],
            'agent_outputs': agent_outputs,
            'planning': planning_result['response']
        }
    
    async def _execute_agent(
        self, 
        agent: Agent, 
        input_text: str, 
        context: Dict
    ) -> Dict[str, Any]:
        """Execute a single agent"""
        from agents.execution import AgentFactory
        
        agent_instance = AgentFactory.create_agent(agent)
        
        # Add context from previous agents if available
        if context:
            context_str = "\n\nContext from previous agents:\n"
            for agent_id, output in context.items():
                context_str += f"Agent {agent_id}: {output['response'][:200]}...\n"
            input_text = context_str + "\n" + input_text
        
        result = await AgentFactory.execute_agent_async(agent_instance, input_text)
        
        return result
    
    async def _synthesize_responses(self, agent_outputs: Dict[str, Any]) -> str:
        """Synthesize multiple agent outputs into final response"""
        strategy = self.orchestration.workflow_config.get('synthesis_strategy', 'concatenate')
        
        if strategy == 'concatenate':
            # Simple concatenation
            responses = [output['response'] for output in agent_outputs.values()]
            return "\n\n".join(responses)
        
        elif strategy == 'summarize':
            # Use orchestrator to summarize
            from agents.execution import AgentFactory
            
            orchestrator = self.orchestration.orchestrator_agent
            orchestrator_instance = AgentFactory.create_agent(orchestrator)
            
            synthesis_prompt = f"""
            Synthesize these agent responses into a cohesive final answer:
            
            {self._format_agent_outputs(agent_outputs)}
            
            Provide a clear, comprehensive response:
            """
            
            result = await AgentFactory.execute_agent_async(
                orchestrator_instance,
                synthesis_prompt
            )
            
            return result['response']
        
        elif strategy == 'vote':
            # Majority voting (for classification/decision tasks)
            responses = [output['response'] for output in agent_outputs.values()]
            from collections import Counter
            most_common = Counter(responses).most_common(1)
            return most_common[0][0] if most_common else responses[0]
        
        else:
            return agent_outputs[list(agent_outputs.keys())[0]]['response']
    
    def _format_agent_outputs(self, agent_outputs: Dict[str, Any]) -> str:
        """Format agent outputs for display"""
        formatted = []
        for agent_id, output in agent_outputs.items():
            agent = Agent.objects.get(id=agent_id)
            formatted.append(f"**{agent.name}**: {output['response']}")
        return "\n\n".join(formatted)
    
    def _log_communication(self, from_agent_id: int, to_agent_id: int, content: str):
        """Log communication between agents"""
        AgentCommunication.objects.create(
            execution=self.execution,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type='response',
            content=content
        )
    
    def _update_average_execution_time(self, execution_time_ms: float):
        """Update running average of execution time"""
        total = self.orchestration.total_executions
        if total == 0:
            self.orchestration.average_execution_time_ms = int(execution_time_ms)
        else:
            current_avg = self.orchestration.average_execution_time_ms
            new_avg = ((current_avg * total) + execution_time_ms) / (total + 1)
            self.orchestration.average_execution_time_ms = int(new_avg)
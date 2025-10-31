"""
Agent execution with LangChain integration.
Phase 5: Enhanced with RAG (Retrieval-Augmented Generation) support.
Phase 6: Integrated with Business Use Case Tools.
"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import Tool
from django.conf import settings
from typing import List, Dict, Optional, Any, Callable
import logging
import asyncio
from datetime import datetime
from agents.models import Agent, ToolExecution

logger = logging.getLogger(__name__)


# ============================================================================
# TOOL REGISTRY 
# ============================================================================

class ToolRegistry:
    """Enhanced registry for pluggable tools including Phase 6 business use case tools."""
    
    _tools = {}
    _use_case_tools = {}  # Maps use cases to their tools
    _tool_instances = {}  # Cache for tool instances
    
    @classmethod
    def register_tool(cls, name: str, tool_func: Callable, use_cases: List[str] = None):
        """
        Register a tool by name.
        
        Args:
            name: Unique tool identifier
            tool_func: Tool function or class
            use_cases: List of use cases this tool applies to
        """
        cls._tools[name] = tool_func
        
        # Track tools by use case for Phase 6
        if use_cases:
            for use_case in use_cases:
                if use_case not in cls._use_case_tools:
                    cls._use_case_tools[use_case] = []
                cls._use_case_tools[use_case].append({
                    'name': name,
                    'tool': tool_func
                })

    @classmethod
    def get_tools(cls) -> List:
        """Return all registered LangChain-compatible tools."""
        return [tool for tool in cls._tools.values() 
                if hasattr(tool, 'invoke') or callable(tool)]

    @classmethod
    def get_tool(cls, name: str):
        """Get a specific tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def get_tools_for_use_case(cls, use_case: str) -> List:
        """
        Get all tools registered for a specific use case.
        
        Args:
            use_case: The use case identifier (support, research, etc.)
            
        Returns:
            List of tool dictionaries with name and tool class
        """
        return cls._use_case_tools.get(use_case, [])
    
    @classmethod
    def create_tool_instance(cls, name: str, agent: Agent, **kwargs):
        """
        Create an instance of a Phase 6 tool class.
        
        Args:
            name: Tool name
            agent: Agent model instance
            **kwargs: Additional tool configuration
            
        Returns:
            Tool instance or None if tool doesn't exist
        """
        tool_class = cls._tools.get(name)
        if not tool_class:
            return None
        
        # Check if it's a Phase 6 class-based tool
        if hasattr(tool_class, '__call__') and not hasattr(tool_class, 'invoke'):
            try:
                # It's a Phase 6 tool class, instantiate it
                return tool_class(agent=agent, **kwargs)
            except Exception as e:
                logger.error(f"Error creating tool instance {name}: {e}")
                return None
        else:
            # It's a LangChain function tool, return as-is
            return tool_class
    
    @classmethod
    def clear_cache(cls):
        """Clear cached tool instances."""
        cls._tool_instances = {}


# ============================================================================
# DEFAULT LANGCHAIN TOOLS (Phase 1-5)
# ============================================================================

def search_knowledge_base(query: str) -> str:
    """
    Search the agent's knowledge base for relevant information.
    
    Args:
        query: Search query
        
    Returns:
        Relevant information from knowledge base
    """
    # This is a placeholder - actual implementation would use vector search
    return f"Searched knowledge base for: {query}"

def schedule_meeting(date: str, time: str, attendees: str) -> str:
    """
    Schedule a meeting with specified attendees.
    
    Args:
        date: Meeting date (YYYY-MM-DD)
        time: Meeting time (HH:MM)
        attendees: Comma-separated list of attendee emails
        
    Returns:
        Confirmation message
    """
    return f"Meeting scheduled for {date} at {time} with {attendees}"

def send_email(recipient: str, subject: str, body: str) -> str:
    """
    Send an email to specified recipient.
    
    Args:
        recipient: Email address
        subject: Email subject
        body: Email body content
        
    Returns:
        Confirmation message
    """
    return f"Email sent to {recipient} with subject: {subject}"


# Register default tools
ToolRegistry.register_tool("search_knowledge_base", Tool(
    name="search_knowledge_base",
    description="Search the agent's knowledge base for relevant information",
    func=search_knowledge_base
))

ToolRegistry.register_tool("schedule_meeting", Tool(
    name="schedule_meeting",
    description="Schedule a meeting with specified attendees",
    func=schedule_meeting
))

ToolRegistry.register_tool("send_email", Tool(
    name="send_email",
    description="Send an email to a specified recipient",
    func=send_email
))


# ============================================================================
# PHASE 6 TOOL LOADER
# ============================================================================

def load_phase6_tools():
    """
    Attempt to load Phase 6 business use case tools.
    This function is called during app initialization.
    """
    try:
        from agents.tools.use_case_tools import (
            # Support tools
            SentimentAnalyzer,
            EscalationDetector,
            TicketCreator,
            CannedResponseSuggester,
            
            # Research tools
            MultiSourceSearch,
            Summarizer,
            DataExtractor,
            
            # Automation tools
            WorkflowExecutor,
            EmailSender,
            WebhookCaller,
            
            # Scheduling tools
            CalendarManager,
            MeetingScheduler,
            
            # Knowledge tools
            PolicyQA,
            DocumentSearcher,
            
            # Sales tools
            LeadScorer,
            CRMConnector
        )
        
        # Register support tools
        ToolRegistry.register_tool("sentiment_analyzer", SentimentAnalyzer, ["support"])
        ToolRegistry.register_tool("escalation_detector", EscalationDetector, ["support"])
        ToolRegistry.register_tool("ticket_creator", TicketCreator, ["support"])
        ToolRegistry.register_tool("canned_response_suggester", CannedResponseSuggester, ["support"])
        
        # Register research tools
        ToolRegistry.register_tool("multi_source_search", MultiSourceSearch, ["research"])
        ToolRegistry.register_tool("summarizer", Summarizer, ["research"])
        ToolRegistry.register_tool("data_extractor", DataExtractor, ["research"])
        
        # Register automation tools
        ToolRegistry.register_tool("workflow_executor", WorkflowExecutor, ["automation"])
        ToolRegistry.register_tool("email_sender", EmailSender, ["automation", "sales"])
        ToolRegistry.register_tool("webhook_caller", WebhookCaller, ["automation"])
        
        # Register scheduling tools
        ToolRegistry.register_tool("calendar_manager", CalendarManager, ["scheduling"])
        ToolRegistry.register_tool("meeting_scheduler", MeetingScheduler, ["scheduling"])
        
        # Register knowledge tools
        ToolRegistry.register_tool("policy_qa", PolicyQA, ["knowledge"])
        ToolRegistry.register_tool("document_searcher", DocumentSearcher, ["knowledge"])
        
        # Register sales tools
        ToolRegistry.register_tool("lead_scorer", LeadScorer, ["sales"])
        ToolRegistry.register_tool("crm_connector", CRMConnector, ["sales"])
        
        logger.info("Phase 6 business use case tools loaded successfully")
        return True
        
    except ImportError as e:
        logger.info(f"Phase 6 tools not available: {e}")
        return False


# Try to load Phase 6 tools on module import
PHASE6_AVAILABLE = load_phase6_tools()


# ============================================================================
# USE CASE SPECIFIC PROMPTS (Phase 6)
# ============================================================================

USE_CASE_PROMPTS = {
    "support": """You are {agent_name}, a customer support AI assistant.

Your role is to:
- Analyze customer sentiment and emotions
- Provide empathetic, solution-focused responses
- Detect when issues need escalation to human agents
- Suggest relevant help articles and solutions
- Create support tickets when necessary

Always maintain a professional, friendly tone. Prioritize customer satisfaction.
When sentiment is negative, acknowledge frustration and work toward resolution.

Available tools: sentiment analysis, escalation detection, ticket creation, canned responses.""",

    "research": """You are {agent_name}, a research AI assistant.

Your role is to:
- Search multiple data sources for comprehensive information
- Summarize large amounts of text efficiently
- Extract key data points and structured information
- Synthesize findings from various sources
- Provide citations and sources for all information

Focus on accuracy and thoroughness. Present information objectively.
Always cite your sources and indicate confidence levels.

Available tools: multi-source search, text summarization, data extraction.""",

    "automation": """You are {agent_name}, an automation AI assistant.

Your role is to:
- Execute predefined workflows and processes
- Send notifications and emails
- Make API calls to external services
- Coordinate multi-step automated tasks
- Handle errors gracefully and retry when appropriate

Ensure reliable execution and provide detailed status updates.
Log all actions for audit purposes.

Available tools: workflow execution, email sender, webhook caller.""",

    "scheduling": """You are {agent_name}, a scheduling AI assistant.

Your role is to:
- Check calendar availability across multiple participants
- Find optimal meeting times considering all constraints
- Schedule meetings and send invitations
- Handle time zone conversions
- Manage calendar conflicts

Always confirm details before finalizing meetings.
Respect user preferences for meeting times and durations.

Available tools: calendar management, meeting scheduler.""",

    "knowledge": """You are {agent_name}, a knowledge management AI assistant.

Your role is to:
- Answer questions using the company knowledge base
- Search and retrieve relevant documents
- Explain policies and procedures clearly
- Keep information current and accurate
- Suggest related resources

Base all answers on documented information. If unsure, say so.
Direct users to human experts when necessary.

Available tools: policy Q&A, document search.""",

    "sales": """You are {agent_name}, a sales AI assistant.

Your role is to:
- Qualify and score leads based on BANT criteria
- Maintain accurate contact information in CRM
- Provide relevant product information
- Track customer interactions and preferences
- Identify upsell and cross-sell opportunities

Focus on building relationships and providing value.
Never be pushy - guide prospects through their buying journey.

Available tools: lead scoring, CRM connector."""
}


# ============================================================================
# AGENT FACTORY (Enhanced for Phase 6)
# ============================================================================

class AgentFactory:
    """Factory for creating and executing LangChain agents with RAG and Phase 6 tool support."""
    
    @staticmethod
    def create_agent(agent_model: Agent) -> Dict[str, Any]:
        """
        Create a LangChain agent with appropriate LLM, tools, and configuration.
        
        Args:
            agent_model: Agent model instance from database
            
        Returns:
            Dictionary containing agent components:
                - llm: Language model instance
                - chain: LangChain execution chain
                - name: Agent name
                - message_history: Chat history
                - use_case: Agent use case
                - agent_model: Original model instance
                - rag_enabled: Whether RAG is enabled
                - integration: LLM integration
                - tools: Available tools (including Phase 6)
                - phase6_tools: Phase 6 tool instances
        """
        try:
            # Get active LLM integration
            integration = agent_model.integrations.filter(
                integration_type__in=['openai', 'anthropic'], 
                is_active=True
            ).first()
            
            if not integration:
                raise ValueError("No active LLM integration found for this agent")
            
            # Initialize appropriate LLM
            if integration.integration_type == 'openai':
                llm = ChatOpenAI(
                    api_key=integration.api_key,
                    model=integration.settings.get('model', 'gpt-4'),
                    temperature=integration.settings.get('temperature', 0.7),
                )
            elif integration.integration_type == 'anthropic':
                llm = ChatAnthropic(
                    api_key=integration.api_key,
                    model=integration.settings.get('model', 'claude-3-sonnet-20240229'),
                    temperature=integration.settings.get('temperature', 0.7),
                )
            else:
                raise ValueError(f"Unsupported integration type: {integration.integration_type}")
            
            # Get or create optimized prompt template for use case
            if PHASE6_AVAILABLE and agent_model.use_case in USE_CASE_PROMPTS:
                prompt_template = USE_CASE_PROMPTS[agent_model.use_case]
                logger.info(f"Using Phase 6 optimized prompt for {agent_model.use_case}")
            else:
                prompt_template = agent_model.prompt_template or (
                    "You are {agent_name}, a helpful {use_case} AI assistant. "
                    "Assist users with their requests professionally and efficiently."
                )
            
            # Create prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
            
            # Create message history
            message_history = ChatMessageHistory()
            
            # Create base chain
            chain = prompt | llm | RunnablePassthrough()
            
            # Check if RAG is enabled
            rag_enabled = agent_model.knowledge_bases.filter(is_active=True).exists()
            
            # Prepare agent dictionary
            agent_dict = {
                'llm': llm,
                'chain': chain,
                'name': agent_model.name,
                'message_history': message_history,
                'use_case': agent_model.get_use_case_display(),
                'agent_model': agent_model,
                'rag_enabled': rag_enabled,
                'integration': integration,
                'tools': [],
                'phase6_tools': {}
            }
            
            # Load tools if enabled
            if agent_model.get_default_config().get('tools_enabled', False):
                # Get base LangChain tools
                base_tools = ToolRegistry.get_tools()
                
                # Get Phase 6 use-case specific tools
                phase6_tool_configs = ToolRegistry.get_tools_for_use_case(agent_model.use_case)
                
                # Instantiate Phase 6 tools
                phase6_tool_instances = {}
                for tool_config in phase6_tool_configs:
                    tool_name = tool_config['name']
                    tool_class = tool_config['tool']
                    
                    # Get tool-specific config from agent if available
                    tool_kwargs = {}
                    if hasattr(agent_model, 'tools_config'):
                        tool_kwargs = agent_model.tools_config.get(tool_name, {})
                    
                    instance = ToolRegistry.create_tool_instance(
                        tool_name, 
                        agent=agent_model,
                        **tool_kwargs
                    )
                    
                    if instance:
                        phase6_tool_instances[tool_name] = instance
                
                agent_dict['phase6_tools'] = phase6_tool_instances
                
                # Only bind LangChain-compatible tools to chain
                langchain_tools = [t for t in base_tools if hasattr(t, 'invoke')]
                if langchain_tools:
                    agent_dict['chain'] = chain.bind_tools(langchain_tools)
                    agent_dict['tools'] = langchain_tools
                
                logger.info(
                    f"Loaded {len(langchain_tools)} base tools and "
                    f"{len(phase6_tool_instances)} Phase 6 tools for agent {agent_model.name}"
                )
            
            return agent_dict
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_model.name}: {str(e)}")
            raise
    
    @staticmethod
    def _retrieve_knowledge(agent: Dict[str, Any], query: str) -> tuple[str, List[Dict]]:
        """
        Retrieve relevant knowledge from agent's knowledge bases using RAG.
        
        Args:
            agent: Agent dictionary from create_agent
            query: User query for retrieval
            
        Returns:
            Tuple of (context_text, source_documents)
        """
        try:
            from knowledge.services import KnowledgeBaseService
            
            agent_model = agent['agent_model']
            knowledge_bases = agent_model.knowledge_bases.filter(is_active=True)
            
            if not knowledge_bases.exists():
                return "", []
            
            all_results = []
            for kb in knowledge_bases:
                results = KnowledgeBaseService.search_knowledge_base(
                    knowledge_base=kb,
                    query=query,
                    top_k=3
                )
                all_results.extend(results)
            
            # Sort by relevance and take top results
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            top_results = all_results[:5]
            
            # Build context
            context_parts = []
            sources = []
            
            for i, result in enumerate(top_results, 1):
                context_parts.append(f"[Source {i}]\n{result['content']}\n")
                sources.append({
                    'id': result.get('chunk_id'),
                    'document': result.get('document_title', 'Unknown'),
                    'score': result.get('score', 0)
                })
            
            context = "\n".join(context_parts)
            
            logger.info(f"Retrieved {len(top_results)} relevant chunks for query")
            return context, sources
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}")
            return "", []
    
    @staticmethod
    async def _execute_phase6_tools(
        agent: Dict[str, Any], 
        input_text: str, 
        conversation_history: List[Dict]
    ) -> Dict[str, Any]:
        """
        Execute Phase 6 tools based on use case and context.
        
        Args:
            agent: Agent dictionary
            input_text: User input
            conversation_history: List of previous messages
            
        Returns:
            Dictionary with tool execution results
        """
        phase6_results = {}
        agent_model = agent['agent_model']
        use_case = agent_model.use_case
        phase6_tools = agent.get('phase6_tools', {})
        
        if not phase6_tools:
            return phase6_results
        
        try:
            # Support use case: sentiment and escalation
            if use_case == 'support':
                if 'sentiment_analyzer' in phase6_tools:
                    analyzer = phase6_tools['sentiment_analyzer']
                    result = await analyzer.execute(text=input_text)
                    
                    if result.get('success'):
                        phase6_results['sentiment'] = result['data']
                        
                        # Log execution
                        AgentFactory._log_tool_execution(
                            agent_model, 'sentiment_analyzer', 
                            {'text': input_text}, result
                        )
                        
                        # Check for escalation if sentiment is negative
                        if (result['data'].get('requires_escalation') and 
                            'escalation_detector' in phase6_tools):
                            
                            detector = phase6_tools['escalation_detector']
                            escalation_result = await detector.execute(
                                conversation_history=conversation_history,
                                sentiment_score=result['data']['sentiment_score']
                            )
                            
                            if escalation_result.get('success'):
                                phase6_results['escalation'] = escalation_result['data']
                                
                                AgentFactory._log_tool_execution(
                                    agent_model, 'escalation_detector',
                                    {'sentiment_score': result['data']['sentiment_score']},
                                    escalation_result
                                )
            
            # Research use case: search if query indicates research need
            elif use_case == 'research':
                search_triggers = ['search for', 'find', 'research', 'look up', 'what is']
                if any(trigger in input_text.lower() for trigger in search_triggers):
                    if 'multi_source_search' in phase6_tools:
                        searcher = phase6_tools['multi_source_search']
                        result = await searcher.execute(query=input_text)
                        
                        if result.get('success'):
                            phase6_results['search'] = result['data']
                            
                            AgentFactory._log_tool_execution(
                                agent_model, 'multi_source_search',
                                {'query': input_text}, result
                            )
            
            # Sales use case: lead scoring if contact info present
            elif use_case == 'sales':
                # Simple heuristic: if message contains budget/timeline info
                if any(word in input_text.lower() for word in ['budget', 'timeline', 'decision']):
                    if 'lead_scorer' in phase6_tools:
                        # Extract lead data (simplified)
                        scorer = phase6_tools['lead_scorer']
                        result = await scorer.execute(lead_data={
                            'message': input_text,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        if result.get('success'):
                            phase6_results['lead_score'] = result['data']
                            
                            AgentFactory._log_tool_execution(
                                agent_model, 'lead_scorer',
                                {'message': input_text}, result
                            )
            
        except Exception as e:
            logger.error(f"Error executing Phase 6 tools: {e}")
        
        return phase6_results
    
    @staticmethod
    def _log_tool_execution(
        agent_model: Agent, 
        tool_name: str, 
        input_data: Dict, 
        result: Dict
    ):
        """Log tool execution to database."""
        try:
            ToolExecution.objects.create(
                agent=agent_model,
                tool_name=tool_name,
                use_case=agent_model.use_case,
                input_data=input_data,
                output_data=result.get('data', {}),
                success=result.get('success', False),
                execution_time_ms=result.get('execution_time_ms', 0),
                error_message=result.get('error', '')
            )
        except Exception as e:
            logger.error(f"Failed to log tool execution: {e}")
    
    @staticmethod
    async def execute_agent_async(agent: Dict[str, Any], input_text: str) -> Dict[str, Any]:
        """
        Execute agent asynchronously with full Phase 6 support.
        
        Args:
            agent: Agent dictionary from create_agent
            input_text: User input text
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Retrieve knowledge if RAG enabled
            context = ""
            retrieved_sources = []
            
            if agent.get('rag_enabled', False):
                context, retrieved_sources = AgentFactory._retrieve_knowledge(
                    agent=agent,
                    query=input_text
                )
            
            # Execute Phase 6 tools if available
            phase6_results = {}
            if agent.get('phase6_tools'):
                # Convert message history to list format
                history_list = [
                    {
                        'role': 'user' if isinstance(msg, HumanMessage) else 'assistant',
                        'content': msg.content
                    }
                    for msg in agent['message_history'].messages
                ]
                
                phase6_results = await AgentFactory._execute_phase6_tools(
                    agent, input_text, history_list
                )
            
            # Add user message to history
            message_history = agent['message_history']
            message_history.add_user_message(input_text)
            
            # Prepare chain input
            chain_input = {
                'agent_name': agent['name'],
                'use_case': agent['use_case'],
                'history': message_history.messages,
                'input': input_text
            }
            
            # Augment input with context if available
            if context:
                augmented_input = f"""Context from knowledge base:
{context}

User question: {input_text}

Please answer based on the context provided above. If the context doesn't contain relevant information, use your general knowledge but indicate that."""
                chain_input['input'] = augmented_input
            
            # Add Phase 6 tool results to context if available
            if phase6_results:
                tool_context_parts = []
                
                if 'sentiment' in phase6_results:
                    s = phase6_results['sentiment']
                    tool_context_parts.append(
                        f"Customer sentiment: {s['sentiment_level']} "
                        f"(score: {s['sentiment_score']:.2f})"
                    )
                
                if 'escalation' in phase6_results:
                    e = phase6_results['escalation']
                    if e.get('should_escalate'):
                        tool_context_parts.append(
                            f"⚠️ ESCALATION RECOMMENDED: {e['recommendation']}"
                        )
                
                if 'search' in phase6_results:
                    sr = phase6_results['search']
                    tool_context_parts.append(
                        f"Found {sr['total_results']} search results. "
                        f"Summary: {sr.get('summary', 'N/A')[:200]}..."
                    )
                
                if 'lead_score' in phase6_results:
                    ls = phase6_results['lead_score']
                    tool_context_parts.append(
                        f"Lead score: {ls['total_score']:.2f} ({ls['status']}). "
                        f"Recommendation: {ls['recommendation']}"
                    )
                
                if tool_context_parts:
                    tool_context = "\n\n".join(tool_context_parts)
                    chain_input['input'] = f"{tool_context}\n\n{chain_input['input']}"
            
            # Execute chain
            response = await agent['chain'].ainvoke(chain_input)
            
            # Extract response text
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # Add assistant response to history
            message_history.add_ai_message(response_text)
            
            return {
                'response': response_text,
                'sources': retrieved_sources,
                'phase6_results': phase6_results,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error executing agent: {str(e)}")
            return {
                'response': "I apologize, but I encountered an error processing your request.",
                'error': str(e),
                'success': False
            }
    
    @staticmethod
    def execute_agent(agent: Dict[str, Any], input_text: str) -> Dict[str, Any]:
        """
        Execute agent synchronously (wrapper for async method).
        
        Args:
            agent: Agent dictionary from create_agent
            input_text: User input text
            
        Returns:
            Dictionary with response and metadata
        """
        return asyncio.run(AgentFactory.execute_agent_async(agent, input_text))
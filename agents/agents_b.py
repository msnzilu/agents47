"""
Agent execution with LangChain integration.
Phase 5: Enhanced with RAG (Retrieval-Augmented Generation) support.
"""
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.tools import tool
from django.conf import settings
from .models import ToolExecution
import json
from django.db import models
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for pluggable tools."""
    
    _tools = {}

    @classmethod
    def register_tool(cls, name, tool_func):
        """Register a tool by name."""
        cls._tools[name] = tool_func

    @classmethod
    def get_tools(cls):
        """Return all registered tools."""
        return list(cls._tools.values())

    @classmethod
    def get_tool(cls, name):
        """Get a specific tool by name."""
        return cls._tools.get(name)


# Define default tools
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        # Use safe_eval or similar in production
        result = eval(expression, {"__builtins__": {}}, {"sum": sum})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


# Register default tools
ToolRegistry.register_tool('calculator', calculator)

# Uncomment when duckduckgo-search is installed:
# from langchain_community.tools import DuckDuckGoSearchRun
# ToolRegistry.register_tool('web_search', DuckDuckGoSearchRun())


class AgentFactory:
    """Factory for creating and executing LangChain agents with RAG support."""
    
    @staticmethod
    def create_agent(agent_model):
        """
        Create a LangChain agent based on the Agent model.
        
        Phase 5: Now includes RAG capabilities if knowledge bases exist.
        
        :param agent_model: Agent instance from agents.models
        :return: Dict containing agent components
        """
        try:
            # Get LLM integration
            integration = agent_model.integrations.filter(
                integration_type__in=['openai', 'anthropic'], 
                is_active=True
            ).first()
            
            if not integration:
                raise ValueError("No active LLM integration found for this agent")
            
            config = integration.config or {}
            llm_type = integration.integration_type
            
            # Initialize LLM
            if llm_type == 'openai':
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=config.get('api_key'),
                    temperature=agent_model.get_default_config().get('temperature', 0.7),
                    max_tokens=agent_model.get_default_config().get('max_tokens', 1000)
                )
            elif llm_type == 'anthropic':
                llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    api_key=config.get('api_key'),
                    temperature=agent_model.get_default_config().get('temperature', 0.7),
                    max_tokens=agent_model.get_default_config().get('max_tokens', 1000)
                )
            else:
                raise ValueError(f"Unsupported LLM type: {llm_type}")
            
            # Initialize message history
            message_history = InMemoryChatMessageHistory()
            
            # Load conversation history (last 20 messages)
            conversation = agent_model.conversations.filter(is_active=True).last()
            if conversation:
                messages = conversation.messages.order_by('created_at')[:20]
                for msg in messages:
                    if msg.role == 'user':
                        message_history.add_user_message(msg.content)
                    elif msg.role == 'assistant':
                        message_history.add_ai_message(msg.content)
            
            # Define prompt template with history
            # Phase 5: Template now supports context from knowledge base
            prompt_template = agent_model.prompt_template or (
                "You are {agent_name}, a {use_case} AI assistant."
            )
            
            # Add context placeholder if RAG is enabled
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
            
            # Create execution chain
            chain = prompt | llm | RunnablePassthrough()
            
            # Check if RAG is enabled (knowledge bases exist)
            rag_enabled = agent_model.knowledge_bases.filter(
                status='completed'
            ).exists()
            
            # Build agent dictionary
            agent_dict = {
                'llm': llm,
                'chain': chain,
                'name': agent_model.name,
                'message_history': message_history,
                'use_case': agent_model.get_use_case_display(),
                'agent_model': agent_model,
                'rag_enabled': rag_enabled,  # Phase 5: RAG flag
                'integration': integration
            }
            
            # Add tools if enabled
            if agent_model.get_default_config().get('tools_enabled', False):
                agent_dict['tools'] = ToolRegistry.get_tools()
                agent_dict['chain'] = chain.bind_tools(agent_dict['tools'])
            
            logger.info(
                f"Created agent '{agent_model.name}' "
                f"(LLM: {llm_type}, RAG: {rag_enabled})"
            )
            
            return agent_dict
        
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            
            # Fallback to alternate LLM if available
            fallback_integration = agent_model.integrations.filter(
                integration_type=('anthropic' if llm_type == 'openai' else 'openai'),
                is_active=True
            ).first()
            
            if fallback_integration:
                logger.info(f"Falling back to {fallback_integration.integration_type}")
                # Recursive call with fallback
                return AgentFactory.create_agent(agent_model)
            
            raise Exception(f"Agent creation failed: {str(e)}")

    @staticmethod
    def execute_agent(agent, input_text):
        """
        Execute the agent with input.
        
        Phase 5: Now includes RAG - automatically retrieves relevant knowledge
        from the agent's knowledge bases before generating response.
        
        :param agent: Dict containing llm, chain, name, message_history, use_case, agent_model
        :param input_text: User input
        :return: Agent response text
        """
        try:
            # Phase 5: Retrieve relevant knowledge if RAG is enabled
            context = ""
            retrieved_sources = []
            
            if agent.get('rag_enabled', False):
                context, retrieved_sources = AgentFactory._retrieve_knowledge(
                    agent=agent,
                    query=input_text
                )
            
            # Get message history
            message_history = agent['message_history']
            
            # Add user message to history
            message_history.add_user_message(input_text)
            
            # Prepare chain input
            chain_input = {
                'agent_name': agent['name'],
                'use_case': agent['use_case'],
                'history': message_history.messages,
                'input': input_text
            }
            
            # Phase 5: Augment input with context if available
            if context:
                # Enhance the input with retrieved context
                augmented_input = f"""Context from knowledge base:
{context}

User question: {input_text}

Please answer based on the context provided above."""
                chain_input['input'] = augmented_input
                
                logger.info(
                    f"RAG: Retrieved {len(retrieved_sources)} relevant chunks "
                    f"for query: '{input_text[:50]}...'"
                )
            
            # Execute chain with (possibly augmented) input
            response = agent['chain'].invoke(chain_input)
            
            # Handle tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    tool = ToolRegistry.get_tool(tool_name)
                    
                    if tool:
                        result = tool.run(tool_args)
                        
                        # Log tool execution
                        ToolExecution.objects.create(
                            agent=agent['agent_model'],
                            tool_name=tool_name,
                            input_data=tool_args,
                            output_data=result
                        )
                        
                        response.content += f"\nTool {tool_name} result: {result}"
                        logger.info(f"Tool executed: {tool_name}")
            
            # Get response content
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Add assistant message to history
            message_history.add_ai_message(response_text)
            
            # Phase 5: Return response with metadata
            return {
                'text': response_text,
                'sources': retrieved_sources if context else None,
                'rag_used': bool(context)
            } if context else response_text
        
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise

    @staticmethod
    def _retrieve_knowledge(agent, query, limit=3, similarity_threshold=0.7):
        """
        Phase 5: Retrieve relevant knowledge from agent's knowledge bases.
        
        :param agent: Agent dict
        :param query: User query
        :param limit: Maximum number of chunks to retrieve
        :param similarity_threshold: Minimum similarity score
        :return: Tuple of (context_text, sources_list)
        """
        try:
            # Import here to avoid circular imports
            from .services import KnowledgeBaseService
            
            # Search knowledge base
            results = KnowledgeBaseService.search_knowledge_base(
                agent=agent['agent_model'],
                query=query,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            
            if not results:
                logger.debug(f"No relevant knowledge found for query: '{query[:50]}...'")
                return "", []
            
            # Format context from retrieved chunks
            context_parts = []
            sources = []
            
            for idx, result in enumerate(results, 1):
                # Add to context
                context_parts.append(
                    f"[Source {idx}: {result['document_title']}]\n"
                    f"{result['content']}\n"
                )
                
                # Track sources
                sources.append({
                    'title': result['document_title'],
                    'chunk_index': result['chunk_index'],
                    'similarity': result['similarity'],
                    'content_preview': result['content'][:100] + '...'
                })
            
            context = "\n".join(context_parts)
            
            logger.info(
                "RAG: Retrieved {} chunks with similarities: {}".format(
                    len(results),
                    ["{:.2f}".format(s['similarity']) for s in sources]
                )
            )
            
            return context, sources
        
        except Exception as e:
            logger.error(f"Knowledge retrieval failed: {str(e)}")
            # Don't fail the entire request if RAG fails
            return "", []

    @staticmethod
    def execute_agent_streaming(agent, input_text):
        """
        Execute agent with streaming response (for real-time chat).
        Phase 5: Also supports RAG.
        
        :param agent: Agent dict
        :param input_text: User input
        :yield: Response chunks
        """
        try:
            # Phase 5: Retrieve knowledge if RAG enabled
            context = ""
            if agent.get('rag_enabled', False):
                context, _ = AgentFactory._retrieve_knowledge(agent, input_text)
            
            # Get message history
            message_history = agent['message_history']
            message_history.add_user_message(input_text)
            
            # Prepare input
            chain_input = {
                'agent_name': agent['name'],
                'use_case': agent['use_case'],
                'history': message_history.messages,
                'input': input_text
            }
            
            # Augment with context if available
            if context:
                chain_input['input'] = f"""Context from knowledge base:
{context}

User question: {input_text}

Please answer based on the context provided above."""
            
            # Stream response
            full_response = ""
            for chunk in agent['chain'].stream(chain_input):
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    full_response += content
                    yield content
            
            # Add to history
            message_history.add_ai_message(full_response)
        
        except Exception as e:
            logger.error(f"Streaming execution failed: {str(e)}")
            yield f"Error: {str(e)}"


# Phase 5: Helper functions for knowledge base operations

def check_agent_rag_status(agent_model):
    """
    Check if an agent has RAG capabilities enabled.
    
    :param agent_model: Agent instance
    :return: Dict with RAG status information
    """
    completed_kbs = agent_model.knowledge_bases.filter(status='completed')
    
    return {
        'enabled': completed_kbs.exists(),
        'knowledge_bases': completed_kbs.count(),
        'total_chunks': sum(kb.total_chunks for kb in completed_kbs),
        'pending': agent_model.knowledge_bases.filter(status='pending').count(),
        'processing': agent_model.knowledge_bases.filter(status='processing').count(),
        'failed': agent_model.knowledge_bases.filter(status='failed').count()
    }


def get_agent_knowledge_stats(agent_model):
    """
    Get statistics about agent's knowledge base.
    
    :param agent_model: Agent instance
    :return: Dict with knowledge base statistics
    """
    from django.db.models import Count, Sum
    
    stats = agent_model.knowledge_bases.aggregate(
        total=Count('id'),
        completed=Count('id', filter=models.Q(status='completed')),
        total_chunks=Sum('total_chunks')
    )
    
    return {
        'total_documents': stats['total'] or 0,
        'completed_documents': stats['completed'] or 0,
        'total_chunks': stats['total_chunks'] or 0,
        'avg_chunks_per_doc': (
            stats['total_chunks'] / stats['completed'] 
            if stats['completed'] and stats['total_chunks'] 
            else 0
        )
    }


# Export main classes and functions
__all__ = [
    'AgentFactory',
    'ToolRegistry',
    'calculator',
    'check_agent_rag_status',
    'get_agent_knowledge_stats'
]
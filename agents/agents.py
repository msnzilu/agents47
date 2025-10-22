from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.tools import tool
from django.conf import settings
from .models import ToolExecution
import json
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for pluggable tools."""
    
    _tools = {}

    @classmethod
    def register_tool(cls, name, tool):
        """Register a tool by name."""
        cls._tools[name] = tool

    @classmethod
    def get_tools(cls):
        """Return all registered tools."""
        return list(cls._tools.values())

    @classmethod
    def get_tool(cls, name):
        """Get a specific tool by name."""
        return cls._tools.get(name)

# Define tools
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        # Use safe_eval or similar in production
        result = eval(expression, {"__builtins__": {}}, {"sum": sum})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"

# Register tools - only calculator for now
ToolRegistry.register_tool('calculator', calculator)

# Uncomment when duckduckgo-search is installed:
# from langchain_community.tools import DuckDuckGoSearchRun
# ToolRegistry.register_tool('web_search', DuckDuckGoSearchRun())

class AgentFactory:
    """Factory for creating and executing LangChain agents."""
    
    @staticmethod
    def create_agent(agent_model):
        """
        Create a LangChain agent based on the Agent model.
        :param agent_model: Agent instance from agents.models
        """
        try:
            # Get LLM integration
            integration = agent_model.integrations.filter(
                integration_type__in=['openai', 'anthropic'], is_active=True
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
            
            # Load conversation history
            conversation = agent_model.conversations.filter(is_active=True).last()
            if conversation:
                messages = conversation.messages.order_by('created_at')[:20]
                for msg in messages:
                    if msg.role == 'user':
                        message_history.add_user_message(msg.content)
                    elif msg.role == 'assistant':
                        message_history.add_ai_message(msg.content)
            
            # Define prompt template with history
            prompt_template = agent_model.prompt_template or (
                "You are {agent_name}, a {use_case} AI assistant."
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_template),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
            
            # Create execution chain
            chain = prompt | llm | RunnablePassthrough()
            
            # Add tools if enabled
            agent_dict = {
                'llm': llm,
                'chain': chain,
                'name': agent_model.name,
                'message_history': message_history,
                'use_case': agent_model.get_use_case_display(),
                'agent_model': agent_model
            }
            
            if agent_model.get_default_config().get('tools_enabled', False):
                agent_dict['tools'] = ToolRegistry.get_tools()
                agent_dict['chain'] = chain.bind_tools(agent_dict['tools'])
            
            return agent_dict
        
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            # Fallback to alternate LLM
            fallback_integration = agent_model.integrations.filter(
                integration_type=('anthropic' if llm_type == 'openai' else 'openai'),
                is_active=True
            ).first()
            if fallback_integration:
                logger.info(f"Falling back to {fallback_integration.integration_type}")
                return AgentFactory.create_agent(agent_model)
            raise Exception(f"Agent creation failed: {str(e)}")

    @staticmethod
    def execute_agent(agent, input_text):
        """
        Execute the agent with input.
        :param agent: Dict containing llm, chain, name, message_history, use_case, agent_model
        :param input_text: User input
        """
        try:
            # Get message history
            message_history = agent['message_history']
            
            # Add user message to history
            message_history.add_user_message(input_text)
            
            # Execute chain with history
            response = agent['chain'].invoke({
                'agent_name': agent['name'],
                'use_case': agent['use_case'],
                'history': message_history.messages,
                'input': input_text
            })
            
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
            
            # Get response content
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Add assistant message to history
            message_history.add_ai_message(response_text)
            
            return response_text
        
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise
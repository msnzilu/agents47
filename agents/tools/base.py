"""
Base tool classes and registry for AI agents.
Phase 6: Foundation for business use case tools
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.
    """
    
    def __init__(self, agent=None, **kwargs):
        """
        Initialize the tool.
        
        Args:
            agent: The Agent instance this tool belongs to
            **kwargs: Additional configuration
        """
        self.agent = agent
        self.config = kwargs
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def _execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool's main functionality.
        Must be implemented by subclasses.
        
        Returns:
            Dict containing the tool's execution results
        """
        pass
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Public execution method with error handling and logging.
        
        Returns:
            Dict with 'success', 'result', and optional 'error' keys
        """
        try:
            logger.info(f"Executing tool: {self.name}")
            result = await self._execute(**kwargs)
            return {
                'success': True,
                'result': result,
                'tool': self.name
            }
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'tool': self.name
            }
    
    def get_description(self) -> str:
        """Return a description of what this tool does."""
        return self.__doc__ or f"Tool: {self.name}"
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return the parameters this tool accepts."""
        return {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary representation for LLM."""
        return {
            'name': self.name,
            'description': self.get_description(),
            'parameters': self.get_parameters()
        }


class ToolRegistry:
    """
    Central registry for all available tools.
    Maps use cases to their respective tools.
    """
    
    _tools: Dict[str, List[type]] = {}
    _use_case_tools: Dict[str, List[str]] = {
        'support': [
            'SentimentAnalyzer',
            'EscalationDetector',
            'TicketCreator',
            'CannedResponseSuggester'
        ],
        'research': [
            'MultiSourceSearch',
            'Summarizer',
            'DataExtractor',
            'ReportGenerator'
        ],
        'automation': [
            'WorkflowExecutor',
            'EmailSender',
            'WebhookCaller',
            'ScheduleTrigger'
        ],
        'scheduling': [
            'CalendarManager',
            'MeetingScheduler',
            'AvailabilityChecker',
            'ReminderScheduler'
        ],
        'knowledge': [
            'PolicyQA',
            'DocumentSearcher',
            'CrossKBSearch',
            'ConfidenceScorer'
        ],
        'sales': [
            'LeadScorer',
            'CRMConnector',
            'OutreachTemplatePersonalizer',
            'FollowUpReminder'
        ]
    }
    
    @classmethod
    def register(cls, tool_class: type, use_cases: List[str] = None):
        """
        Register a tool class.
        
        Args:
            tool_class: The tool class to register
            use_cases: List of use cases this tool supports
        """
        tool_name = tool_class.__name__
        cls._tools[tool_name] = tool_class
        logger.info(f"Registered tool: {tool_name}")
    
    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[type]:
        """Get a tool class by name."""
        return cls._tools.get(tool_name)
    
    @classmethod
    def get_tools_for_use_case(cls, use_case: str) -> List[Dict[str, Any]]:
        """
        Get all tools available for a specific use case.
        
        Args:
            use_case: The use case name (support, research, etc.)
            
        Returns:
            List of tool dictionaries with name, description, parameters
        """
        tool_names = cls._use_case_tools.get(use_case, [])
        tools = []
        
        for tool_name in tool_names:
            tool_class = cls._tools.get(tool_name)
            if tool_class:
                # Create a temporary instance to get metadata
                try:
                    temp_instance = tool_class(agent=None)
                    tools.append({
                        'name': tool_name.lower().replace('tool', '').replace('_', '_'),
                        'class': tool_class,
                        'description': temp_instance.get_description(),
                        'parameters': temp_instance.get_parameters()
                    })
                except Exception as e:
                    logger.warning(f"Could not instantiate {tool_name}: {e}")
                    tools.append({
                        'name': tool_name.lower(),
                        'class': tool_class,
                        'description': f"Tool: {tool_name}",
                        'parameters': {}
                    })
        
        return tools
    
    @classmethod
    def list_all_tools(cls) -> List[str]:
        """List all registered tool names."""
        return list(cls._tools.keys())
    
    @classmethod
    def list_use_cases(cls) -> List[str]:
        """List all available use cases."""
        return list(cls._use_case_tools.keys())


def tool(name: Optional[str] = None, use_cases: Optional[List[str]] = None):
    """
    Decorator to register a tool class.
    
    Usage:
        @tool(name="my_tool", use_cases=["support"])
        class MyTool(BaseTool):
            async def _execute(self, **kwargs):
                return {"result": "success"}
    
    Args:
        name: Optional custom name for the tool
        use_cases: List of use cases this tool supports
    """
    def decorator(cls):
        # Register the tool
        ToolRegistry.register(cls, use_cases=use_cases)
        
        # Add metadata to the class
        cls._tool_name = name or cls.__name__
        cls._use_cases = use_cases or []
        
        return cls
    
    return decorator


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""
    pass


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found."""
    pass


class ToolConfigurationError(Exception):
    """Raised when a tool is misconfigured."""
    pass


# Helper function to create tool instances
def create_tool(tool_name: str, agent=None, **config) -> BaseTool:
    """
    Factory function to create tool instances.
    
    Args:
        tool_name: Name of the tool to create
        agent: The agent instance
        **config: Tool configuration
        
    Returns:
        Instance of the requested tool
        
    Raises:
        ToolNotFoundError: If tool is not registered
    """
    tool_class = ToolRegistry.get_tool(tool_name)
    if not tool_class:
        raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")
    
    try:
        return tool_class(agent=agent, **config)
    except Exception as e:
        raise ToolConfigurationError(f"Failed to create tool '{tool_name}': {str(e)}")


# Example tool for testing
@tool(name="echo_tool", use_cases=["support", "research"])
class EchoTool(BaseTool):
    """A simple echo tool for testing purposes."""
    
    async def _execute(self, message: str = "") -> Dict[str, Any]:
        """Echo back the input message."""
        return {
            'echo': message,
            'length': len(message)
        }
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'message': {
                'type': 'string',
                'description': 'Message to echo back',
                'required': True
            }
        }
"""
Tools module for Phase 6.
Imports all use case tools and the factory.
"""

# Import all tool modules to trigger registration
from agents.tools.support_tools import *
from agents.tools.research_tools import *
from agents.tools.automation_tools import *
from agents.tools.scheduling_tools import *
from agents.tools.knowledge_tools import *
from agents.tools.sales_tools import *
from agents.tools.use_case_factory import UseCaseAgentFactory

__all__ = [
    # Support Tools
    'SentimentAnalyzer',
    'EscalationDetector',
    'TicketCreator',
    'CannedResponseSuggester',
    # Research Tools
    'MultiSourceSearch',
    'Summarizer',
    'DataExtractor',
    'ReportGenerator',
    # Automation Tools
    'WorkflowExecutor',
    'EmailSender',
    'WebhookCaller',
    'ScheduleTrigger',
    # Scheduling Tools
    'CalendarManager',
    'MeetingScheduler',
    'AvailabilityChecker',
    'ReminderScheduler',
    # Knowledge Tools
    'PolicyQA',
    'DocumentSearcher',
    'CrossKBSearch',
    'ConfidenceScorer',
    # Sales Tools
    'LeadScorer',
    'CRMConnector',
    'OutreachTemplatePersonalizer',
    'FollowUpReminder',
    # Factory
    'UseCaseAgentFactory'
]
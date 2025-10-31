"""
Factory for use case specific agent configurations.
Manages prompts, tool assignments, and configurations for each use case.
"""

from typing import Dict, List, Optional


class UseCaseAgentFactory:
    """
    Factory for use case specific agent configurations.
    Provides prompt templates, tool configurations, and agent settings for each use case.
    """
    
    PROMPT_TEMPLATES = {
        'support': """You are an empathetic customer support agent.
Analyze sentiment, detect escalations, and create tickets when needed.
Always prioritize customer satisfaction and escalate when uncertain.""",
        
        'research': """You are a thorough research analyst.
Search multiple sources, extract data, and provide well-cited information.
Always cite your sources and cross-reference important claims.""",
        
        'automation': """You are a reliable automation agent.
Execute workflows, send emails, and make webhook calls precisely.
Validate configurations and handle errors gracefully.""",
        
        'scheduling': """You are an efficient scheduling assistant.
Check availability, schedule meetings, and handle timezone conversions.
Always confirm details before finalizing schedules.""",
        
        'knowledge': """You are a knowledgeable information specialist.
Answer policy questions accurately and search documentation thoroughly.
Clearly indicate confidence levels and cite sources.""",
        
        'sales': """You are a strategic sales assistant.
Score leads using BANT, look up CRM data, and personalize outreach.
Focus on qualification and high-quality engagement."""
    }
    
    USE_CASE_CONFIGS = {
        'support': {
            'tools': ['sentiment_analyzer', 'escalation_detector', 'ticket_creator', 'canned_response_suggester'],
            'escalation_threshold': -0.7,
            'auto_escalate': True
        },
        'research': {
            'tools': ['multi_source_search', 'summarizer', 'data_extractor', 'report_generator'],
            'max_sources': 10,
            'citation_required': True
        },
        'automation': {
            'tools': ['workflow_executor', 'email_sender', 'webhook_caller', 'schedule_trigger'],
            'max_retries': 3,
            'timeout_seconds': 300
        },
        'scheduling': {
            'tools': ['calendar_manager', 'meeting_scheduler', 'availability_checker', 'reminder_scheduler'],
            'default_duration': 30,
            'buffer_minutes': 15
        },
        'knowledge': {
            'tools': ['policy_qa', 'document_searcher', 'cross_kb_search', 'confidence_scorer'],
            'min_confidence': 0.7,
            'max_results': 5
        },
        'sales': {
            'tools': ['lead_scorer', 'crm_connector', 'outreach_template_personalizer', 'follow_up_reminder'],
            'hot_lead_threshold': 80,
            'warm_lead_threshold': 50
        }
    }
    
    @classmethod
    def get_prompt_template(cls, use_case: str) -> str:
        """Get prompt template for use case."""
        return cls.PROMPT_TEMPLATES.get(
            use_case,
            "You are a helpful AI assistant."
        )
    
    @classmethod
    def get_use_case_config(cls, use_case: str) -> Dict:
        """Get configuration for use case."""
        return cls.USE_CASE_CONFIGS.get(use_case, {})
    
    @classmethod
    def get_tool_names(cls, use_case: str) -> List[str]:
        """Get tool names for use case."""
        config = cls.get_use_case_config(use_case)
        return config.get('tools', [])
    
    @classmethod
    def create_agent_prompt(cls, use_case: str, custom_instructions: Optional[str] = None) -> str:
        """Create complete agent prompt."""
        base_prompt = cls.get_prompt_template(use_case)
        if custom_instructions:
            return f"{base_prompt}\n\nAdditional Instructions:\n{custom_instructions}"
        return base_prompt
    
    @classmethod
    def list_use_cases(cls) -> List[str]:
        """List all available use cases."""
        return list(cls.PROMPT_TEMPLATES.keys())
    
    @classmethod
    def validate_use_case(cls, use_case: str) -> bool:
        """Check if use case is valid."""
        return use_case in cls.PROMPT_TEMPLATES


__all__ = ['UseCaseAgentFactory']
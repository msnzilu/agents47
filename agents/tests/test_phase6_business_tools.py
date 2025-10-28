# tests/test_phase6_business_tools.py
"""
Comprehensive test suite for Phase 6: Business Use Case Tools
Tests all tools for support, research, automation, scheduling, knowledge, and sales use cases
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

# Import all tools (adjust import paths based on your project structure)
from agents.tools.base import ToolRegistry, BaseTool
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
    CRMConnector,
    
    # Factory
    UseCaseAgentFactory
)


# ============================================================================
# SUPPORT USE CASE TESTS
# ============================================================================

class TestSentimentAnalyzer:
    """Test sentiment analysis tool"""
    
    @pytest.fixture
    def analyzer(self):
        return SentimentAnalyzer()
    
    @pytest.mark.asyncio
    async def test_detect_negative_sentiment(self, analyzer):
        """Test detection of negative sentiment"""
        text = "This is terrible! I'm extremely frustrated and angry with your service."
        result = await analyzer.execute(text=text)
        
        assert result["success"] is True
        data = result["data"]
        assert data["sentiment_score"] < 0
        assert data["sentiment_level"] in ["negative", "very_negative"]
        assert data["urgency_level"] in ["high", "critical"]
        assert len(data["emotional_indicators"]) > 0
    
    @pytest.mark.asyncio
    async def test_detect_positive_sentiment(self, analyzer):
        """Test detection of positive sentiment"""
        text = "Thank you so much! Your service is excellent and I really appreciate the help."
        result = await analyzer.execute(text=text)
        
        data = result["data"]
        assert data["sentiment_score"] > 0
        assert data["sentiment_level"] in ["positive", "very_positive"]
        assert any("positive" in indicator for indicator in data["emotional_indicators"])
    
    @pytest.mark.asyncio
    async def test_escalation_trigger(self, analyzer):
        """Test escalation detection in very negative messages"""
        text = "This is unacceptable! I've been waiting for hours and nothing works! I want my money back NOW!"
        result = await analyzer.execute(text=text)
        
        data = result["data"]
        assert data["requires_escalation"] is True
        assert data["urgency_level"] in ["high", "critical"]
    
    @pytest.mark.asyncio
    async def test_neutral_sentiment(self, analyzer):
        """Test neutral sentiment detection"""
        text = "I would like to know more about your pricing plans."
        result = await analyzer.execute(text=text)
        
        data = result["data"]
        assert -0.2 <= data["sentiment_score"] <= 0.2
        assert data["sentiment_level"] == "neutral"


class TestEscalationDetector:
    """Test escalation detection tool"""
    
    @pytest.fixture
    def detector(self):
        return EscalationDetector()
    
    @pytest.mark.asyncio
    async def test_legal_threat_escalation(self, detector):
        """Test escalation on legal threats"""
        conversation = [
            {"role": "user", "content": "I'm going to contact my lawyer about this!"},
            {"role": "assistant", "content": "I understand your frustration..."}
        ]
        
        result = await detector.execute(
            conversation_history=conversation,
            sentiment_score=-0.8
        )
        
        data = result["data"]
        assert data["should_escalate"] is True
        assert any(t["type"] == "legal_threat" for t in data["triggers"])
        assert "legal team" in data["recommendation"].lower()
    
    @pytest.mark.asyncio
    async def test_long_conversation_escalation(self, detector):
        """Test escalation for long unresolved conversations"""
        # Create a long conversation
        conversation = [
            {"role": "user" if i % 2 == 0 else "assistant", 
             "content": f"Message {i}"}
            for i in range(25)
        ]
        
        result = await detector.execute(
            conversation_history=conversation,
            sentiment_score=-0.3
        )
        
        data = result["data"]
        assert any(t["type"] == "long_conversation" for t in data["triggers"])
    
    @pytest.mark.asyncio
    async def test_no_escalation_needed(self, detector):
        """Test when escalation is not needed"""
        conversation = [
            {"role": "user", "content": "Can you help me reset my password?"},
            {"role": "assistant", "content": "Of course! I can help with that."}
        ]
        
        result = await detector.execute(
            conversation_history=conversation,
            sentiment_score=0.0
        )
        
        data = result["data"]
        assert data["should_escalate"] is False
        assert data["confidence"] < 0.5


class TestCannedResponseSuggester:
    """Test canned response suggestion tool"""
    
    @pytest.fixture
    def suggester(self):
        return CannedResponseSuggester()
    
    @pytest.mark.asyncio
    async def test_password_reset_suggestion(self, suggester):
        """Test suggestion for password reset queries"""
        message = "I forgot my password and can't login"
        result = await suggester.execute(message=message)
        
        data = result["data"]
        assert len(data["suggestions"]) > 0
        assert data["best_match"]["type"] == "password_reset"
        assert "password" in data["best_match"]["response"].lower()
    
    @pytest.mark.asyncio
    async def test_multiple_suggestions(self, suggester):
        """Test multiple relevant suggestions"""
        message = "Hi, I have a billing issue and need help"
        result = await suggester.execute(message=message)
        
        data = result["data"]
        assert len(data["suggestions"]) >= 2
        assert any(s["type"] == "billing_inquiry" for s in data["suggestions"])
        assert any(s["type"] == "general_greeting" for s in data["suggestions"])


# ============================================================================
# RESEARCH USE CASE TESTS
# ============================================================================

class TestMultiSourceSearch:
    """Test multi-source search tool"""
    
    @pytest.fixture
    def searcher(self):
        return MultiSourceSearch()
    
    @pytest.mark.asyncio
    async def test_search_all_sources(self, searcher):
        """Test searching across all sources"""
        result = await searcher.execute(query="artificial intelligence trends")
        
        data = result["data"]
        assert data["query"] == "artificial intelligence trends"
        assert len(data["sources_searched"]) > 0
        assert data["total_results"] > 0
        assert "summary" in data
    
    @pytest.mark.asyncio
    async def test_search_specific_sources(self, searcher):
        """Test searching specific sources only"""
        result = await searcher.execute(
            query="climate change",
            sources=["academic", "news"]
        )
        
        data = result["data"]
        assert set(data["sources_searched"]) == {"academic", "news"}
        assert all(r["source_type"] in ["academic", "news"] for r in data["results"])


class TestSummarizer:
    """Test text summarization tool"""
    
    @pytest.fixture
    def summarizer(self):
        return Summarizer()
    
    @pytest.mark.asyncio
    async def test_bullet_summary(self, summarizer):
        """Test bullet point summarization"""
        text = "This is a long document. " * 50
        result = await summarizer.execute(text=text, style="bullet")
        
        data = result["data"]
        assert "•" in data["summary"]
        assert len(data["summary"]) < len(text)
        assert data["style"] == "bullet"
    
    @pytest.mark.asyncio
    async def test_paragraph_summary(self, summarizer):
        """Test paragraph summarization"""
        text = "Important information. " * 30
        result = await summarizer.execute(text=text, style="paragraph")
        
        data = result["data"]
        assert "•" not in data["summary"]
        assert data["style"] == "paragraph"
        assert "compression_ratio" in data


class TestDataExtractor:
    """Test data extraction tool"""
    
    @pytest.fixture
    def extractor(self):
        return DataExtractor()
    
    @pytest.mark.asyncio
    async def test_extract_dates(self, extractor):
        """Test date extraction"""
        text = "The meeting is on 12/25/2024 and the deadline is 01/15/2025."
        result = await extractor.execute(text=text, extract_types=["dates"])
        
        data = result["data"]
        assert "dates" in data["extracted_data"]
        assert "12/25/2024" in data["extracted_data"]["dates"]
        assert "01/15/2025" in data["extracted_data"]["dates"]
    
    @pytest.mark.asyncio
    async def test_extract_emails(self, extractor):
        """Test email extraction"""
        text = "Contact john@example.com or support@company.org for help."
        result = await extractor.execute(text=text, extract_types=["emails"])
        
        data = result["data"]
        assert "emails" in data["extracted_data"]
        assert "john@example.com" in data["extracted_data"]["emails"]
        assert "support@company.org" in data["extracted_data"]["emails"]


# ============================================================================
# AUTOMATION USE CASE TESTS
# ============================================================================

class TestWorkflowExecutor:
    """Test workflow execution tool"""
    
    @pytest.fixture
    def executor(self):
        return WorkflowExecutor()
    
    @pytest.mark.asyncio
    async def test_simple_workflow(self, executor):
        """Test execution of a simple workflow"""
        workflow = {
            "id": "test_workflow",
            "steps": [
                {"type": "action", "name": "Step 1", "action": {"type": "log", "message": "Starting"}},
                {"type": "wait", "name": "Wait", "duration": 0.1},
                {"type": "action", "name": "Step 2", "action": {"type": "notify", "recipient": "user"}}
            ]
        }
        
        result = await executor.execute(workflow_config=workflow)
        
        data = result["data"]
        assert data["success"] is True
        assert data["executed_steps"] == 3
        assert all(r["success"] for r in data["results"])
    
    @pytest.mark.asyncio
    async def test_workflow_with_failure(self, executor):
        """Test workflow handling failures"""
        workflow = {
            "id": "failing_workflow",
            "steps": [
                {"type": "action", "name": "Good Step", "action": {"type": "log"}},
                {"type": "unknown", "name": "Bad Step", "stop_on_failure": True},
                {"type": "action", "name": "Never Reached", "action": {"type": "log"}}
            ]
        }
        
        result = await executor.execute(workflow_config=workflow)
        
        data = result["data"]
        assert data["success"] is False
        assert data["executed_steps"] == 2  # Stopped after failure


class TestEmailSender:
    """Test email sending tool"""
    
    @pytest.fixture
    def sender(self):
        return EmailSender()
    
    @pytest.mark.asyncio
    async def test_send_welcome_email(self, sender):
        """Test sending welcome email with template"""
        result = await sender.execute(
            recipient="user@example.com",
            template="welcome",
            variables={"name": "John", "company": "Acme Corp"}
        )
        
        data = result["data"]
        assert data["success"] is True
        assert data["email"]["to"] == "user@example.com"
        assert "Welcome to Acme Corp" in data["email"]["subject"]
        assert "John" in data["email"]["body"]
    
    @pytest.mark.asyncio
    async def test_send_custom_notification(self, sender):
        """Test sending custom notification email"""
        result = await sender.execute(
            recipient="admin@example.com",
            template="notification",
            variables={
                "name": "Admin",
                "title": "System Alert",
                "message": "Server maintenance scheduled"
            }
        )
        
        data = result["data"]
        assert data["success"] is True
        assert "System Alert" in data["email"]["subject"]


# ============================================================================
# SCHEDULING USE CASE TESTS
# ============================================================================

class TestCalendarManager:
    """Test calendar management tool"""
    
    @pytest.fixture
    def manager(self):
        return CalendarManager()
    
    @pytest.mark.asyncio
    async def test_check_availability(self, manager):
        """Test checking calendar availability"""
        start = datetime.now().replace(hour=9, minute=0)
        end = start + timedelta(days=2)
        
        result = await manager.execute(
            action="check_availability",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            duration_minutes=60
        )
        
        data = result["data"]
        assert "available_slots" in data
        assert len(data["available_slots"]) > 0
        assert data["duration_minutes"] == 60
    
    @pytest.mark.asyncio
    async def test_create_event(self, manager):
        """Test creating calendar event"""
        start_time = datetime.now() + timedelta(days=1)
        
        result = await manager.execute(
            action="create_event",
            title="Team Meeting",
            start_time=start_time.isoformat(),
            duration_minutes=30,
            attendees=["alice@example.com", "bob@example.com"],
            description="Weekly sync"
        )
        
        data = result["data"]
        assert data["success"] is True
        assert data["event"]["title"] == "Team Meeting"
        assert len(data["event"]["attendees"]) == 2


class TestMeetingScheduler:
    """Test meeting scheduling tool"""
    
    @pytest.fixture
    def scheduler(self):
        return MeetingScheduler()
    
    @pytest.mark.asyncio
    async def test_find_meeting_time(self, scheduler):
        """Test finding optimal meeting time"""
        result = await scheduler.execute(
            participants=["user1@example.com", "user2@example.com"],
            duration_minutes=60,
            preferences={"time_zone": "UTC", "earliest": "09:00", "latest": "17:00"}
        )
        
        data = result["data"]
        assert len(data["suggested_times"]) > 0
        assert data["best_time"] is not None
        assert data["duration_minutes"] == 60
        assert data["timezone"] == "UTC"


# ============================================================================
# KNOWLEDGE USE CASE TESTS
# ============================================================================

class TestPolicyQA:
    """Test policy Q&A tool"""
    
    @pytest.fixture
    def qa_tool(self):
        return PolicyQA()
    
    @pytest.mark.asyncio
    async def test_answer_policy_question(self, qa_tool):
        """Test answering policy-related questions"""
        result = await qa_tool.execute(question="What is the refund policy?")
        
        data = result["data"]
        assert "answer" in data
        assert data["confidence"] > 0
        assert "refund" in data["answer"].lower()
        assert "sources" in data
    
    @pytest.mark.asyncio
    async def test_unknown_policy(self, qa_tool):
        """Test handling unknown policy questions"""
        result = await qa_tool.execute(question="What is the policy on unicorns?")
        
        data = result["data"]
        assert data["confidence"] < 0.5
        assert "couldn't find" in data["answer"].lower() or "contact support" in data["answer"].lower()


class TestDocumentSearcher:
    """Test document search tool"""
    
    @pytest.fixture
    def searcher(self):
        return DocumentSearcher()
    
    @pytest.mark.asyncio
    async def test_search_documents(self, searcher):
        """Test document search functionality"""
        result = await searcher.execute(query="employee handbook", limit=5)
        
        data = result["data"]
        assert "results" in data
        assert len(data["results"]) <= 5
        assert data["query"] == "employee handbook"
        assert all("relevance" in r for r in data["results"])
    
    @pytest.mark.asyncio
    async def test_filtered_search(self, searcher):
        """Test document search with filters"""
        result = await searcher.execute(
            query="policy",
            filters={"document_type": "policy"},
            limit=10
        )
        
        data = result["data"]
        assert all(r["document_type"] == "policy" for r in data["results"])
        assert data["filters_applied"] == {"document_type": "policy"}


# ============================================================================
# SALES USE CASE TESTS
# ============================================================================

class TestLeadScorer:
    """Test lead scoring tool"""
    
    @pytest.fixture
    def scorer(self):
        return LeadScorer()
    
    @pytest.mark.asyncio
    async def test_score_hot_lead(self, scorer):
        """Test scoring a hot lead"""
        lead_data = {
            "id": "lead_001",
            "budget": 150000,
            "timeline_days": 15,
            "authority": "decision_maker",
            "need": "critical"
        }
        
        result = await scorer.execute(lead_data=lead_data)
        
        data = result["data"]
        assert data["status"] == "hot"
        assert data["total_score"] >= 0.8
        assert "immediate follow-up" in data["recommendation"].lower()
    
    @pytest.mark.asyncio
    async def test_score_cold_lead(self, scorer):
        """Test scoring a cold lead"""
        lead_data = {
            "id": "lead_002",
            "budget": 5000,
            "timeline_days": 365,
            "authority": "user",
            "need": "nice_to_have"
        }
        
        result = await scorer.execute(lead_data=lead_data)
        
        data = result["data"]
        assert data["status"] == "cold"
        assert data["total_score"] < 0.4
        assert "nurture" in data["recommendation"].lower()


class TestCRMConnector:
    """Test CRM connector tool"""
    
    @pytest.fixture
    def connector(self):
        return CRMConnector()
    
    @pytest.mark.asyncio
    async def test_lookup_contact(self, connector):
        """Test looking up contact in CRM"""
        result = await connector.execute(
            action="lookup",
            email="john.doe@example.com",
            company="Example Corp"
        )
        
        data = result["data"]
        assert data["found"] is True
        assert data["contact"]["email"] == "john.doe@example.com"
        assert "id" in data["contact"]
    
    @pytest.mark.asyncio
    async def test_create_contact(self, connector):
        """Test creating new contact in CRM"""
        result = await connector.execute(
            action="create",
            email="new.lead@example.com",
            name="New Lead",
            company="New Company",
            phone="+1234567890"
        )
        
        data = result["data"]
        assert data["success"] is True
        assert "contact_id" in data
        assert data["created_data"]["email"] == "new.lead@example.com"


# ============================================================================
# USE CASE INTEGRATION TESTS
# ============================================================================

class TestUseCaseIntegration:
    """Test integration of tools with use cases"""
    
    def test_support_tools_registered(self):
        """Test that support tools are properly registered"""
        support_tools = ToolRegistry.get_tools_for_use_case("support")
        tool_names = [tool.name for tool in support_tools]
        
        assert "sentiment_analyzer" in tool_names
        assert "escalation_detector" in tool_names
        assert "ticket_creator" in tool_names
        assert "canned_response_suggester" in tool_names
    
    def test_research_tools_registered(self):
        """Test that research tools are properly registered"""
        research_tools = ToolRegistry.get_tools_for_use_case("research")
        tool_names = [tool.name for tool in research_tools]
        
        assert "multi_source_search" in tool_names
        assert "summarizer" in tool_names
        assert "data_extractor" in tool_names
    
    def test_use_case_prompt_templates(self):
        """Test that each use case has appropriate prompt template"""
        use_cases = ["support", "research", "automation", "scheduling", "knowledge", "sales"]
        
        for use_case in use_cases:
            template = UseCaseAgentFactory.get_prompt_template(use_case)
            assert template is not None
            assert len(template) > 50  # Ensure it's not just a placeholder
            assert use_case in template.lower() or "assistant" in template.lower()
    
    @pytest.mark.asyncio
    async def test_tool_chaining(self):
        """Test chaining multiple tools together"""
        # First analyze sentiment
        analyzer = SentimentAnalyzer()
        sentiment_result = await analyzer.execute(
            text="I'm very upset about this recurring issue!"
        )
        
        # Then check for escalation
        detector = EscalationDetector()
        escalation_result = await detector.execute(
            conversation_history=[
                {"role": "user", "content": "This is the third time this happened!"}
            ],
            sentiment_score=sentiment_result["data"]["sentiment_score"]
        )
        
        # Finally create a ticket if needed
        if escalation_result["data"]["should_escalate"]:
            creator = TicketCreator()
            ticket_result = await creator.execute(
                customer_id="customer_123",
                issue_summary="Recurring issue with high negative sentiment",
                priority="high",
                category="escalation"
            )
            
            assert ticket_result["data"]["success"] is True
            assert ticket_result["data"]["ticket"]["priority"] == "high"
    
    def test_tool_execution_time(self):
        """Test that all tools complete within acceptable time"""
        import time
        
        async def measure_execution_time(tool: BaseTool, **kwargs):
            start = time.time()
            await tool.execute(**kwargs)
            return time.time() - start
        
        # Test a few tools
        tools_to_test = [
            (SentimentAnalyzer(), {"text": "Test message"}),
            (LeadScorer(), {"lead_data": {"budget": 10000}}),
            (PolicyQA(), {"question": "What is the policy?"})
        ]
        
        for tool, kwargs in tools_to_test:
            execution_time = asyncio.run(measure_execution_time(tool, **kwargs))
            assert execution_time < 3.0, f"{tool.name} took too long: {execution_time}s"


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance benchmarks for tools"""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_sentiment_analysis_performance(self):
        """Benchmark sentiment analysis performance"""
        analyzer = SentimentAnalyzer()
        text = "This is a test message. " * 100  # Long text
        
        start = datetime.now()
        for _ in range(10):
            await analyzer.execute(text=text)
        duration = (datetime.now() - start).total_seconds()
        
        assert duration < 1.0, f"10 analyses took {duration}s, should be < 1s"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_tool_execution(self):
        """Test concurrent execution of multiple tools"""
        tools_and_params = [
            (SentimentAnalyzer(), {"text": "Test message"}),
            (LeadScorer(), {"lead_data": {"budget": 50000}}),
            (PolicyQA(), {"question": "Policy question"}),
            (EmailSender(), {"recipient": "test@example.com", "template": "welcome"}),
            (CalendarManager(), {"action": "check_availability", 
                               "start_date": datetime.now().isoformat(),
                               "end_date": (datetime.now() + timedelta(days=1)).isoformat()})
        ]
        
        start = datetime.now()
        
        # Execute all tools concurrently
        tasks = [tool.execute(**params) for tool, params in tools_and_params]
        results = await asyncio.gather(*tasks)
        
        duration = (datetime.now() - start).total_seconds()
        
        assert all(r["success"] for r in results)
        assert duration < 2.0, f"Concurrent execution took {duration}s, should be < 2s"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in tools"""
    
    @pytest.mark.asyncio
    async def test_invalid_input_handling(self):
        """Test tools handle invalid inputs gracefully"""
        analyzer = SentimentAnalyzer()
        result = await analyzer.execute(text="")  # Empty text
        
        # Should still return a result, not crash
        assert "success" in result
        if result["success"]:
            assert result["data"]["sentiment_level"] == "neutral"
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test tool timeout handling"""
        executor = WorkflowExecutor()
        executor.timeout_seconds = 0.001  # Very short timeout
        
        workflow = {
            "steps": [
                {"type": "wait", "duration": 10}  # Will timeout
            ]
        }
        
        result = await executor.execute(workflow_config=workflow)
        
        assert result["success"] is False
        assert "timeout" in result.get("error", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
# Phase 6: Business Use Case Tools - Complete Implementation
# This file contains all the specialized tools for each business use case

"""
agents/tools/use_case_tools.py
Complete implementation of all business use case tools for Phase 6
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from agents.tools.base import BaseTool, tool, ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# SUPPORT USE CASE TOOLS
# ============================================================================

@tool(
    name="escalation_detector",
    description="Detects when a support conversation needs escalation",
    use_cases=["support"]
)
class EscalationDetector(BaseTool):
    """Detects when customer issues need to be escalated to a supervisor"""
    
    ESCALATION_TRIGGERS = {
        "legal_threat": ["lawyer", "sue", "legal action", "court", "lawsuit"],
        "refund_demand": ["refund", "money back", "chargeback", "dispute"],
        "competitor_mention": ["competitor", "switch", "cancel", "leave"],
        "executive_request": ["ceo", "president", "executive", "manager"],
        "repeated_issue": ["again", "still not working", "multiple times", "keeps happening"]
    }
    
    async def _execute(self, 
                      conversation_history: List[Dict], 
                      sentiment_score: float = 0.0) -> Dict[str, Any]:
        """
        Analyze conversation for escalation triggers
        
        Args:
            conversation_history: List of previous messages
            sentiment_score: Current sentiment score
            
        Returns:
            Escalation decision with confidence and reasons
        """
        triggers_found = []
        confidence = 0.0
        
        # Check recent messages for triggers
        recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
        
        for message in recent_messages:
            if message.get("role") == "user":
                text_lower = message.get("content", "").lower()
                
                for trigger_type, keywords in self.ESCALATION_TRIGGERS.items():
                    for keyword in keywords:
                        if keyword in text_lower:
                            triggers_found.append({
                                "type": trigger_type,
                                "keyword": keyword,
                                "message": text_lower[:100]
                            })
                            confidence += 0.2
        
        # Factor in sentiment
        if sentiment_score < -0.5:
            confidence += 0.3
            triggers_found.append({"type": "negative_sentiment", "score": sentiment_score})
        
        # Check conversation length (long unresolved issues)
        if len(conversation_history) > 20:
            confidence += 0.2
            triggers_found.append({"type": "long_conversation", "length": len(conversation_history)})
        
        should_escalate = confidence >= 0.5
        
        return {
            "should_escalate": should_escalate,
            "confidence": min(confidence, 1.0),
            "triggers": triggers_found,
            "recommendation": self._get_recommendation(should_escalate, triggers_found)
        }
    
    def _get_recommendation(self, should_escalate: bool, triggers: List[Dict]) -> str:
        """Generate escalation recommendation"""
        if not should_escalate:
            return "Continue handling at current level"
        
        if any(t["type"] == "legal_threat" for t in triggers):
            return "URGENT: Escalate to legal team immediately"
        elif any(t["type"] == "executive_request" for t in triggers):
            return "Escalate to senior management"
        else:
            return "Escalate to supervisor for review"


@tool(
    name="ticket_creator",
    description="Creates support tickets in CRM system",
    use_cases=["support"]
)
class TicketCreator(BaseTool):
    """Creates and manages support tickets"""
    
    async def _execute(self,
                      customer_id: str,
                      issue_summary: str,
                      priority: str = "medium",
                      category: str = "general") -> Dict[str, Any]:
        """
        Create a support ticket
        
        Args:
            customer_id: Customer identifier
            issue_summary: Brief description of the issue
            priority: Ticket priority (low/medium/high/urgent)
            category: Issue category
            
        Returns:
            Ticket creation details
        """
        # In production, this would integrate with actual CRM
        ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{hash(customer_id) % 10000:04d}"
        
        ticket_data = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "issue_summary": issue_summary,
            "priority": priority,
            "category": category,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "assigned_to": None,
            "integration": "stub"  # Would be actual CRM in production
        }
        
        # Log ticket creation (would save to database)
        logger.info(f"Ticket created: {ticket_id}")
        
        return {
            "success": True,
            "ticket": ticket_data,
            "message": f"Ticket {ticket_id} created successfully"
        }


@tool(
    name="canned_response_suggester",
    description="Suggests appropriate canned responses based on issue type",
    use_cases=["support"]
)
class CannedResponseSuggester(BaseTool):
    """Suggests pre-written responses for common issues"""
    
    RESPONSE_TEMPLATES = {
        "password_reset": {
            "keywords": ["password", "reset", "forgot", "login"],
            "response": "I can help you reset your password. Please click on the 'Forgot Password' link on the login page. You'll receive an email with instructions to create a new password."
        },
        "billing_inquiry": {
            "keywords": ["billing", "invoice", "payment", "charge"],
            "response": "I understand you have a billing inquiry. Let me review your account details. Can you please provide your account number or the email associated with your account?"
        },
        "technical_issue": {
            "keywords": ["not working", "error", "bug", "broken", "issue"],
            "response": "I'm sorry you're experiencing technical difficulties. To help resolve this, could you please describe: 1) What you were trying to do, 2) Any error messages you saw, 3) What device/browser you're using?"
        },
        "refund_request": {
            "keywords": ["refund", "money back", "return"],
            "response": "I understand you'd like to request a refund. Our refund policy allows returns within 30 days of purchase. Let me check your order details to see how we can help."
        },
        "general_greeting": {
            "keywords": ["hello", "hi", "help"],
            "response": "Hello! Welcome to our support team. How can I assist you today?"
        }
    }
    
    async def _execute(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Suggest canned responses based on the customer message
        
        Args:
            message: Customer message
            context: Optional conversation context
            
        Returns:
            Suggested responses with confidence scores
        """
        message_lower = message.lower()
        suggestions = []
        
        for response_type, template in self.RESPONSE_TEMPLATES.items():
            score = 0
            matched_keywords = []
            
            for keyword in template["keywords"]:
                if keyword in message_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                confidence = min(score / len(template["keywords"]), 1.0)
                suggestions.append({
                    "type": response_type,
                    "response": template["response"],
                    "confidence": confidence,
                    "matched_keywords": matched_keywords
                })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "suggestions": suggestions[:3],  # Return top 3 suggestions
            "best_match": suggestions[0] if suggestions else None,
            "total_matches": len(suggestions)
        }


# ============================================================================
# RESEARCH USE CASE TOOLS
# ============================================================================

@tool(
    name="multi_source_search",
    description="Searches multiple sources and aggregates results",
    use_cases=["research"]
)
class MultiSourceSearch(BaseTool):
    """Searches across multiple sources for comprehensive research"""
    
    SOURCES = ["web", "academic", "news", "social"]
    
    async def _execute(self, query: str, sources: List[str] = None) -> Dict[str, Any]:
        """
        Search across multiple sources
        
        Args:
            query: Search query
            sources: List of sources to search (default: all)
            
        Returns:
            Aggregated search results from multiple sources
        """
        sources = sources or self.SOURCES
        results = {}
        
        # Simulate searches (in production, would use actual APIs)
        for source in sources:
            if source == "web":
                results[source] = await self._search_web(query)
            elif source == "academic":
                results[source] = await self._search_academic(query)
            elif source == "news":
                results[source] = await self._search_news(query)
            elif source == "social":
                results[source] = await self._search_social(query)
        
        # Aggregate and rank results
        aggregated = self._aggregate_results(results)
        
        return {
            "query": query,
            "sources_searched": sources,
            "results": aggregated,
            "total_results": sum(len(r) for r in results.values()),
            "summary": self._generate_research_summary(aggregated)
        }
    
    async def _search_web(self, query: str) -> List[Dict]:
        """Simulate web search"""
        # In production, use actual search API
        return [
            {"title": f"Web result for {query}", "url": "http://example.com", "snippet": "Sample web result"}
        ]
    
    async def _search_academic(self, query: str) -> List[Dict]:
        """Simulate academic search"""
        return [
            {"title": f"Academic paper on {query}", "journal": "Sample Journal", "abstract": "Sample abstract"}
        ]
    
    async def _search_news(self, query: str) -> List[Dict]:
        """Simulate news search"""
        return [
            {"title": f"News about {query}", "source": "News Source", "date": datetime.now().isoformat()}
        ]
    
    async def _search_social(self, query: str) -> List[Dict]:
        """Simulate social media search"""
        return [
            {"platform": "Twitter", "content": f"Discussion about {query}", "engagement": 100}
        ]
    
    def _aggregate_results(self, results: Dict[str, List]) -> List[Dict]:
        """Aggregate and rank results from all sources"""
        aggregated = []
        
        for source, items in results.items():
            for item in items:
                item["source_type"] = source
                aggregated.append(item)
        
        return aggregated
    
    def _generate_research_summary(self, results: List[Dict]) -> str:
        """Generate a summary of research findings"""
        source_counts = {}
        for result in results:
            source = result.get("source_type")
            source_counts[source] = source_counts.get(source, 0) + 1
        
        summary = f"Found {len(results)} results across {len(source_counts)} sources. "
        summary += "Distribution: " + ", ".join([f"{k}: {v}" for k, v in source_counts.items()])
        
        return summary


@tool(
    name="summarizer",
    description="Summarizes long texts into concise summaries",
    use_cases=["research"]
)
class Summarizer(BaseTool):
    """Creates summaries of varying lengths from long texts"""
    
    async def _execute(self,
                      text: str,
                      max_length: int = 200,
                      style: str = "bullet") -> Dict[str, Any]:
        """
        Summarize text
        
        Args:
            text: Text to summarize
            max_length: Maximum summary length in words
            style: Summary style (bullet/paragraph/abstract)
            
        Returns:
            Summary in requested format
        """
        # Simple extractive summarization (in production, use NLP model)
        sentences = text.split('.')
        
        # Score sentences by importance (simplified)
        scored_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) > 10:
                # Simple scoring based on length and position
                score = len(sentence.split()) / 100 + (1.0 if sentences.index(sentence) < 3 else 0.5)
                scored_sentences.append((sentence.strip(), score))
        
        # Sort by score and select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        if style == "bullet":
            summary_points = [f"• {sent[0]}" for sent in scored_sentences[:5]]
            summary = "\n".join(summary_points)
        elif style == "paragraph":
            summary_sentences = [sent[0] for sent in scored_sentences[:3]]
            summary = ". ".join(summary_sentences) + "."
        else:  # abstract
            summary = f"Abstract: {scored_sentences[0][0] if scored_sentences else 'No content to summarize'}"
        
        return {
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
            "compression_ratio": f"{(1 - len(summary) / len(text)) * 100:.1f}%",
            "summary": summary,
            "style": style
        }


@tool(
    name="data_extractor",
    description="Extracts structured data from unstructured text",
    use_cases=["research"]
)
class DataExtractor(BaseTool):
    """Extracts specific data points from text"""
    
    async def _execute(self,
                      text: str,
                      extract_types: List[str] = None) -> Dict[str, Any]:
        """
        Extract structured data from text
        
        Args:
            text: Source text
            extract_types: Types of data to extract (dates/numbers/entities/emails/urls)
            
        Returns:
            Extracted data organized by type
        """
        extract_types = extract_types or ["dates", "numbers", "emails", "urls"]
        extracted = {}
        
        if "dates" in extract_types:
            # Extract dates (simplified)
            date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
            extracted["dates"] = re.findall(date_pattern, text)
        
        if "numbers" in extract_types:
            # Extract numbers with context
            number_pattern = r'\b\d+\.?\d*\b'
            numbers = re.findall(number_pattern, text)
            extracted["numbers"] = [{"value": n, "context": self._get_context(text, n)} for n in numbers[:10]]
        
        if "emails" in extract_types:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            extracted["emails"] = re.findall(email_pattern, text)
        
        if "urls" in extract_types:
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            extracted["urls"] = re.findall(url_pattern, text)
        
        if "entities" in extract_types:
            # Simple entity extraction (proper nouns)
            extracted["entities"] = self._extract_entities(text)
        
        return {
            "extracted_data": extracted,
            "extraction_types": extract_types,
            "total_items": sum(len(v) if isinstance(v, list) else 1 for v in extracted.values())
        }
    
    def _get_context(self, text: str, item: str, window: int = 20) -> str:
        """Get context around an extracted item"""
        index = text.find(str(item))
        if index == -1:
            return ""
        start = max(0, index - window)
        end = min(len(text), index + len(str(item)) + window)
        return "..." + text[start:end] + "..."
    
    def _extract_entities(self, text: str) -> List[str]:
        """Simple entity extraction based on capitalization"""
        words = text.split()
        entities = []
        
        for i, word in enumerate(words):
            # Check if word is capitalized and not at sentence start
            if word and word[0].isupper() and (i == 0 or words[i-1][-1] not in '.!?'):
                entities.append(word.strip('.,!?;:'))
        
        return list(set(entities))[:20]  # Return unique entities


# ============================================================================
# AUTOMATION USE CASE TOOLS
# ============================================================================

@tool(
    name="workflow_executor",
    description="Executes automated workflows based on JSON configuration",
    use_cases=["automation"]
)
class WorkflowExecutor(BaseTool):
    """Executes multi-step automated workflows"""
    
    async def _execute(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow based on configuration
        
        Args:
            workflow_config: JSON configuration defining workflow steps
            
        Returns:
            Workflow execution results
        """
        workflow_id = workflow_config.get("id", f"wf_{datetime.now().timestamp()}")
        steps = workflow_config.get("steps", [])
        results = []
        
        logger.info(f"Starting workflow {workflow_id} with {len(steps)} steps")
        
        for i, step in enumerate(steps):
            step_result = await self._execute_step(step, i, results)
            results.append(step_result)
            
            # Check if step failed and should stop workflow
            if not step_result["success"] and step.get("stop_on_failure", True):
                logger.error(f"Workflow {workflow_id} stopped at step {i} due to failure")
                break
        
        return {
            "workflow_id": workflow_id,
            "total_steps": len(steps),
            "executed_steps": len(results),
            "success": all(r["success"] for r in results),
            "results": results,
            "execution_time": sum(r.get("duration", 0) for r in results)
        }
    
    async def _execute_step(self, step: Dict, index: int, previous_results: List[Dict]) -> Dict:
        """Execute a single workflow step"""
        step_type = step.get("type")
        step_name = step.get("name", f"Step {index}")
        
        start_time = datetime.now()
        
        try:
            if step_type == "condition":
                result = self._evaluate_condition(step.get("condition", {}), previous_results)
            elif step_type == "action":
                result = await self._perform_action(step.get("action", {}))
            elif step_type == "wait":
                await asyncio.sleep(step.get("duration", 1))
                result = {"waited": step.get("duration", 1)}
            else:
                result = {"error": f"Unknown step type: {step_type}"}
            
            success = "error" not in result
        except Exception as e:
            result = {"error": str(e)}
            success = False
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            "step": step_name,
            "type": step_type,
            "success": success,
            "result": result,
            "duration": duration
        }
    
    def _evaluate_condition(self, condition: Dict, previous_results: List[Dict]) -> Dict:
        """Evaluate a workflow condition"""
        # Simple condition evaluation
        condition_type = condition.get("type")
        
        if condition_type == "equals":
            left = condition.get("left")
            right = condition.get("right")
            result = left == right
            return {"condition_met": result}
        
        return {"condition_met": True}
    
    async def _perform_action(self, action: Dict) -> Dict:
        """Perform a workflow action"""
        action_type = action.get("type")
        
        if action_type == "log":
            message = action.get("message", "Workflow action executed")
            logger.info(message)
            return {"logged": message}
        elif action_type == "notify":
            return {"notified": action.get("recipient", "user")}
        
        return {"action": action_type}


@tool(
    name="email_sender",
    description="Sends automated emails with templates",
    use_cases=["automation"]
)
class EmailSender(BaseTool):
    """Sends templated emails"""
    
    EMAIL_TEMPLATES = {
        "welcome": {
            "subject": "Welcome to {company}!",
            "body": "Hi {name},\n\nWelcome to {company}! We're excited to have you on board.\n\nBest regards,\nThe Team"
        },
        "reminder": {
            "subject": "Reminder: {event}",
            "body": "Hi {name},\n\nThis is a friendly reminder about {event} on {date}.\n\nSee you there!"
        },
        "notification": {
            "subject": "Notification: {title}",
            "body": "Hi {name},\n\n{message}\n\nThank you!"
        }
    }
    
    async def _execute(self,
                      recipient: str,
                      template: str = "notification",
                      variables: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Send an email using a template
        
        Args:
            recipient: Email recipient
            template: Template name
            variables: Template variables
            
        Returns:
            Email send status
        """
        variables = variables or {}
        template_data = self.EMAIL_TEMPLATES.get(template, self.EMAIL_TEMPLATES["notification"])
        
        # Replace variables in template
        subject = template_data["subject"]
        body = template_data["body"]
        
        for key, value in variables.items():
            subject = subject.replace(f"{{{key}}}", str(value))
            body = body.replace(f"{{{key}}}", str(value))
        
        # In production, would use actual email service
        email_data = {
            "to": recipient,
            "subject": subject,
            "body": body,
            "sent_at": datetime.now().isoformat(),
            "template": template,
            "status": "sent"  # In production, would get actual status
        }
        
        logger.info(f"Email sent to {recipient} using template '{template}'")
        
        return {
            "success": True,
            "email": email_data,
            "message": f"Email sent successfully to {recipient}"
        }


@tool(
    name="webhook_caller",
    description="Calls external webhooks with authentication",
    use_cases=["automation"]
)
class WebhookCaller(BaseTool):
    """Calls external webhooks"""
    
    async def _execute(self,
                      url: str,
                      method: str = "POST",
                      payload: Dict[str, Any] = None,
                      headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Call an external webhook
        
        Args:
            url: Webhook URL
            method: HTTP method
            payload: Request payload
            headers: Request headers
            
        Returns:
            Webhook response
        """
        # In production, would use aiohttp or requests
        
        # Simulate webhook call
        webhook_response = {
            "status_code": 200,
            "response": {"message": "Webhook received"},
            "headers": {"content-type": "application/json"}
        }
        
        logger.info(f"Webhook called: {method} {url}")
        
        return {
            "success": webhook_response["status_code"] < 400,
            "url": url,
            "method": method,
            "status_code": webhook_response["status_code"],
            "response": webhook_response["response"],
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# SCHEDULING USE CASE TOOLS
# ============================================================================

@tool(
    name="calendar_manager",
    description="Manages calendar events and availability",
    use_cases=["scheduling"]
)
class CalendarManager(BaseTool):
    """Manages calendar operations"""
    
    async def _execute(self,
                      action: str,
                      **kwargs) -> Dict[str, Any]:
        """
        Perform calendar operations
        
        Args:
            action: Calendar action (check_availability/create_event/update_event/cancel_event)
            **kwargs: Action-specific parameters
            
        Returns:
            Calendar operation result
        """
        if action == "check_availability":
            return await self._check_availability(**kwargs)
        elif action == "create_event":
            return await self._create_event(**kwargs)
        elif action == "update_event":
            return await self._update_event(**kwargs)
        elif action == "cancel_event":
            return await self._cancel_event(**kwargs)
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _check_availability(self,
                                 start_date: str,
                                 end_date: str,
                                 duration_minutes: int = 60) -> Dict[str, Any]:
        """Check calendar availability"""
        # In production, would integrate with Google Calendar API
        
        # Simulate availability slots
        available_slots = []
        current = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        while current < end:
            # Skip weekends
            if current.weekday() < 5:
                # Check business hours (9 AM - 5 PM)
                if 9 <= current.hour < 17:
                    available_slots.append({
                        "start": current.isoformat(),
                        "end": (current + timedelta(minutes=duration_minutes)).isoformat()
                    })
            
            current += timedelta(hours=1)
        
        return {
            "available_slots": available_slots[:10],  # Return first 10 slots
            "total_slots": len(available_slots),
            "duration_minutes": duration_minutes
        }
    
    async def _create_event(self,
                          title: str,
                          start_time: str,
                          duration_minutes: int = 60,
                          attendees: List[str] = None,
                          description: str = "") -> Dict[str, Any]:
        """Create calendar event"""
        event_id = f"evt_{hash(title + start_time) % 100000:05d}"
        
        event = {
            "id": event_id,
            "title": title,
            "start": start_time,
            "end": (datetime.fromisoformat(start_time) + timedelta(minutes=duration_minutes)).isoformat(),
            "attendees": attendees or [],
            "description": description,
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "event": event,
            "message": f"Event '{title}' created successfully"
        }
    
    async def _update_event(self, event_id: str, **updates) -> Dict[str, Any]:
        """Update calendar event"""
        return {
            "success": True,
            "event_id": event_id,
            "updates": updates,
            "message": f"Event {event_id} updated successfully"
        }
    
    async def _cancel_event(self, event_id: str, notify_attendees: bool = True) -> Dict[str, Any]:
        """Cancel calendar event"""
        return {
            "success": True,
            "event_id": event_id,
            "notified": notify_attendees,
            "message": f"Event {event_id} cancelled successfully"
        }


@tool(
    name="meeting_scheduler",
    description="Schedules meetings with conflict detection",
    use_cases=["scheduling"]
)
class MeetingScheduler(BaseTool):
    """Schedules meetings intelligently"""
    
    async def _execute(self,
                      participants: List[str],
                      duration_minutes: int,
                      preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Find optimal meeting time for all participants
        
        Args:
            participants: List of participant emails
            duration_minutes: Meeting duration
            preferences: Scheduling preferences (time_zone, earliest, latest)
            
        Returns:
            Optimal meeting times
        """
        preferences = preferences or {}
        
        # Simulate finding common availability
        suggested_times = []
        
        # Generate suggestions (in production, check actual calendars)
        base_time = datetime.now() + timedelta(days=1)
        base_time = base_time.replace(hour=10, minute=0, second=0, microsecond=0)
        
        for i in range(3):
            meeting_time = base_time + timedelta(days=i)
            suggested_times.append({
                "start": meeting_time.isoformat(),
                "end": (meeting_time + timedelta(minutes=duration_minutes)).isoformat(),
                "conflicts": [],
                "score": 0.9 - (i * 0.1)  # Earlier times get higher scores
            })
        
        return {
            "participants": participants,
            "duration_minutes": duration_minutes,
            "suggested_times": suggested_times,
            "best_time": suggested_times[0] if suggested_times else None,
            "timezone": preferences.get("time_zone", "UTC")
        }


# ============================================================================
# KNOWLEDGE USE CASE TOOLS
# ============================================================================

@tool(
    name="policy_qa",
    description="Answers questions about policies and procedures",
    use_cases=["knowledge"]
)
class PolicyQA(BaseTool):
    """Answers policy-related questions"""
    
    async def _execute(self,
                      question: str,
                      knowledge_base_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer policy questions using knowledge base
        
        Args:
            question: User question
            knowledge_base_id: Specific knowledge base to search
            
        Returns:
            Answer with confidence and sources
        """
        # In production, would use actual RAG with vector search
        
        # Simulate policy search
        mock_policies = {
            "refund": "Our refund policy allows returns within 30 days of purchase with original receipt.",
            "privacy": "We protect user data in accordance with GDPR and CCPA regulations.",
            "vacation": "Employees are entitled to 15 days of paid vacation per year.",
            "security": "All data is encrypted at rest and in transit using industry standards."
        }
        
        # Simple keyword matching
        question_lower = question.lower()
        matched_policies = []
        
        for policy_key, policy_text in mock_policies.items():
            if policy_key in question_lower:
                matched_policies.append({
                    "policy": policy_key,
                    "text": policy_text,
                    "confidence": 0.8
                })
        
        if matched_policies:
            answer = matched_policies[0]["text"]
            confidence = matched_policies[0]["confidence"]
        else:
            answer = "I couldn't find a specific policy matching your question. Please contact support for more information."
            confidence = 0.2
        
        return {
            "question": question,
            "answer": answer,
            "confidence": confidence,
            "sources": [m["policy"] for m in matched_policies],
            "knowledge_base": knowledge_base_id
        }


@tool(
    name="document_searcher",
    description="Searches across all knowledge bases",
    use_cases=["knowledge"]
)
class DocumentSearcher(BaseTool):
    """Searches documents across knowledge bases"""
    
    async def _execute(self,
                      query: str,
                      filters: Dict[str, Any] = None,
                      limit: int = 10) -> Dict[str, Any]:
        """
        Search documents
        
        Args:
            query: Search query
            filters: Search filters (document_type, date_range, etc.)
            limit: Maximum results
            
        Returns:
            Search results with relevance scores
        """
        # In production, would use vector search with embeddings
        
        # Simulate document search
        mock_results = [
            {
                "document_id": f"doc_{i}",
                "title": f"Document about {query} - Part {i}",
                "snippet": f"This document contains information about {query}...",
                "relevance": 0.9 - (i * 0.05),
                "document_type": "policy" if i % 2 == 0 else "guide"
            }
            for i in range(min(5, limit))
        ]
        
        # Apply filters if provided
        if filters:
            if "document_type" in filters:
                mock_results = [r for r in mock_results if r["document_type"] == filters["document_type"]]
        
        return {
            "query": query,
            "results": mock_results,
            "total_results": len(mock_results),
            "filters_applied": filters or {},
            "search_time_ms": 150  # Simulated search time
        }


# ============================================================================
# SALES USE CASE TOOLS
# ============================================================================

@tool(
    name="lead_scorer",
    description="Scores leads based on qualification criteria",
    use_cases=["sales"]
)
class LeadScorer(BaseTool):
    """Scores and qualifies leads"""
    
    SCORING_CRITERIA = {
        "budget": {"weight": 0.3, "thresholds": {"high": 100000, "medium": 50000, "low": 10000}},
        "timeline": {"weight": 0.2, "thresholds": {"immediate": 30, "soon": 90, "future": 180}},
        "authority": {"weight": 0.25, "levels": {"decision_maker": 1.0, "influencer": 0.6, "user": 0.3}},
        "need": {"weight": 0.25, "levels": {"critical": 1.0, "important": 0.7, "nice_to_have": 0.3}}
    }
    
    async def _execute(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a lead based on BANT criteria
        
        Args:
            lead_data: Lead information including budget, timeline, authority, need
            
        Returns:
            Lead score and qualification status
        """
        score = 0
        criteria_scores = {}
        
        # Budget scoring
        budget = lead_data.get("budget", 0)
        if budget >= self.SCORING_CRITERIA["budget"]["thresholds"]["high"]:
            budget_score = 1.0
        elif budget >= self.SCORING_CRITERIA["budget"]["thresholds"]["medium"]:
            budget_score = 0.7
        elif budget >= self.SCORING_CRITERIA["budget"]["thresholds"]["low"]:
            budget_score = 0.4
        else:
            budget_score = 0.1
        
        criteria_scores["budget"] = budget_score * self.SCORING_CRITERIA["budget"]["weight"]
        
        # Timeline scoring
        timeline_days = lead_data.get("timeline_days", 365)
        if timeline_days <= self.SCORING_CRITERIA["timeline"]["thresholds"]["immediate"]:
            timeline_score = 1.0
        elif timeline_days <= self.SCORING_CRITERIA["timeline"]["thresholds"]["soon"]:
            timeline_score = 0.7
        elif timeline_days <= self.SCORING_CRITERIA["timeline"]["thresholds"]["future"]:
            timeline_score = 0.4
        else:
            timeline_score = 0.1
        
        criteria_scores["timeline"] = timeline_score * self.SCORING_CRITERIA["timeline"]["weight"]
        
        # Authority scoring
        authority = lead_data.get("authority", "user")
        authority_score = self.SCORING_CRITERIA["authority"]["levels"].get(authority, 0.3)
        criteria_scores["authority"] = authority_score * self.SCORING_CRITERIA["authority"]["weight"]
        
        # Need scoring
        need = lead_data.get("need", "nice_to_have")
        need_score = self.SCORING_CRITERIA["need"]["levels"].get(need, 0.3)
        criteria_scores["need"] = need_score * self.SCORING_CRITERIA["need"]["weight"]
        
        # Calculate total score
        total_score = sum(criteria_scores.values())
        
        # Determine qualification status
        if total_score >= 0.8:
            status = "hot"
            recommendation = "High priority - immediate follow-up recommended"
        elif total_score >= 0.6:
            status = "warm"
            recommendation = "Medium priority - schedule follow-up within 48 hours"
        elif total_score >= 0.4:
            status = "cool"
            recommendation = "Low priority - nurture with automated campaigns"
        else:
            status = "cold"
            recommendation = "Not qualified - add to long-term nurture list"
        
        return {
            "lead_id": lead_data.get("id", "unknown"),
            "total_score": round(total_score, 2),
            "status": status,
            "criteria_scores": criteria_scores,
            "recommendation": recommendation,
            "scoring_date": datetime.now().isoformat()
        }


@tool(
    name="crm_connector",
    description="Connects to CRM for contact lookup and updates",
    use_cases=["sales"]
)
class CRMConnector(BaseTool):
    """CRM integration tool"""
    
    async def _execute(self,
                      action: str,
                      **kwargs) -> Dict[str, Any]:
        """
        Perform CRM operations
        
        Args:
            action: CRM action (lookup/create/update)
            **kwargs: Action-specific parameters
            
        Returns:
            CRM operation result
        """
        if action == "lookup":
            return await self._lookup_contact(**kwargs)
        elif action == "create":
            return await self._create_contact(**kwargs)
        elif action == "update":
            return await self._update_contact(**kwargs)
        else:
            return {"error": f"Unknown CRM action: {action}"}
    
    async def _lookup_contact(self, email: str = None, company: str = None) -> Dict[str, Any]:
        """Lookup contact in CRM"""
        # Simulate CRM lookup
        if email:
            contact = {
                "id": f"contact_{hash(email) % 10000:04d}",
                "email": email,
                "name": email.split('@')[0].title(),
                "company": company or "Unknown Company",
                "last_activity": datetime.now().isoformat(),
                "deal_stage": "prospecting"
            }
            
            return {
                "found": True,
                "contact": contact,
                "source": "crm_stub"
            }
        
        return {
            "found": False,
            "message": "Contact not found in CRM"
        }
    
    async def _create_contact(self, **contact_data) -> Dict[str, Any]:
        """Create contact in CRM"""
        contact_id = f"contact_{datetime.now().timestamp()}"
        
        return {
            "success": True,
            "contact_id": contact_id,
            "created_data": contact_data,
            "message": "Contact created successfully"
        }
    
    async def _update_contact(self, contact_id: str, **updates) -> Dict[str, Any]:
        """Update contact in CRM"""
        return {
            "success": True,
            "contact_id": contact_id,
            "updates": updates,
            "message": "Contact updated successfully"
        }


# ============================================================================
# USE CASE AGENT CONFIGURATIONS
# ============================================================================

class UseCaseAgentFactory:
    """Factory for creating agents with use-case specific tools"""
    
    @staticmethod
    def get_tools_for_use_case(use_case: str) -> List[BaseTool]:
        """Get all tools for a specific use case"""
        return ToolRegistry.get_tools_for_use_case(use_case)
    
    @staticmethod
    def get_prompt_template(use_case: str) -> str:
        """Get optimized prompt template for use case"""
        templates = {
            "support": """You are a helpful customer support agent. You have access to sentiment analysis, 
                         escalation detection, and ticket creation tools. Always be empathetic and solution-focused. 
                         Monitor customer sentiment and escalate when necessary.""",
            
            "research": """You are a research assistant with access to multi-source search, summarization, 
                          and data extraction tools. Provide comprehensive, well-sourced information. 
                          Always cite your sources and indicate confidence levels.""",
            
            "automation": """You are an automation specialist with workflow execution, email, and webhook tools. 
                           Help users automate repetitive tasks efficiently. Always confirm actions before execution.""",
            
            "scheduling": """You are a scheduling assistant with calendar and meeting management tools. 
                           Help coordinate schedules and find optimal meeting times. Always consider time zones.""",
            
            "knowledge": """You are a knowledge management assistant with access to policy Q&A and document search. 
                          Provide accurate information from the knowledge base. Always cite sources.""",
            
            "sales": """You are a sales assistant with lead scoring and CRM tools. Help qualify leads 
                       and manage the sales pipeline. Focus on identifying high-value opportunities."""
        }
        
        return templates.get(use_case, "You are a helpful AI assistant.")


# Register all tools when module is imported
def register_all_tools():
    """Register all business use case tools"""
    # Tools are automatically registered via the @tool decorator
    pass

# Initialize tool registration
register_all_tools()
# agents/tools/support/sentiment.py
"""
Sentiment analysis tool for customer support use case.
Analyzes customer messages to detect emotional tone and urgency.
"""

from typing import Dict, Any, List
from agents.tools.base import BaseTool, tool
from dataclasses import dataclass
from enum import Enum
import re


class SentimentLevel(Enum):
    """Sentiment levels for customer messages"""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class UrgencyLevel(Enum):
    """Urgency levels for customer messages"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SentimentAnalysis:
    """Result of sentiment analysis"""
    text: str
    sentiment_score: float  # -1.0 to 1.0
    sentiment_level: SentimentLevel
    urgency_level: UrgencyLevel
    subjectivity: float  # 0.0 to 1.0
    key_phrases: List[str]
    emotional_indicators: List[str]
    requires_escalation: bool
    confidence: float


@tool(
    name="sentiment_analyzer",
    description="Analyzes customer sentiment and emotional tone in messages",
    use_cases=["support"]
)
class SentimentAnalyzer(BaseTool):
    """
    Analyzes sentiment in customer support messages to help agents
    understand emotional context and prioritize responses.
    """
    
    # Keywords indicating urgency
    URGENT_KEYWORDS = [
        "urgent", "emergency", "critical", "immediately", "asap",
        "right now", "crisis", "breaking", "stopped working",
        "completely broken", "losing money", "can't work"
    ]
    
    # Keywords indicating strong negative emotion
    NEGATIVE_KEYWORDS = [
        "angry", "frustrated", "disappointed", "upset", "terrible",
        "horrible", "worst", "unacceptable", "disgusting", "pathetic",
        "ridiculous", "waste", "useless", "broken", "failed"
    ]
    
    # Keywords indicating positive emotion
    POSITIVE_KEYWORDS = [
        "thank", "appreciate", "great", "excellent", "wonderful",
        "fantastic", "amazing", "perfect", "love", "best",
        "helpful", "solved", "fixed", "working"
    ]
    
    def _setup(self):
        """Initialize sentiment analysis components"""
        self.escalation_threshold = self.config.get('escalation_threshold', -0.5)
    
    def _calculate_sentiment_score(self, text: str) -> float:
        """Calculate sentiment score from text"""
        text_lower = text.lower()
        
        # Count positive and negative keywords
        positive_count = sum(1 for word in self.POSITIVE_KEYWORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text_lower)
        
        # Simple scoring algorithm
        total_words = len(text.split())
        if total_words == 0:
            return 0.0
        
        score = (positive_count - negative_count) / max(total_words * 0.1, 1)
        return max(-1.0, min(1.0, score))
    
    def _calculate_sentiment_level(self, score: float) -> SentimentLevel:
        """Convert numerical score to sentiment level"""
        if score <= -0.6:
            return SentimentLevel.VERY_NEGATIVE
        elif score <= -0.2:
            return SentimentLevel.NEGATIVE
        elif score <= 0.2:
            return SentimentLevel.NEUTRAL
        elif score <= 0.6:
            return SentimentLevel.POSITIVE
        else:
            return SentimentLevel.VERY_POSITIVE
    
    def _detect_urgency(self, text: str) -> UrgencyLevel:
        """Detect urgency level in the message"""
        text_lower = text.lower()
        
        # Count urgent keywords
        urgent_count = sum(1 for keyword in self.URGENT_KEYWORDS if keyword in text_lower)
        
        # Check for multiple exclamation marks or caps
        exclamation_count = text.count('!')
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        
        # Determine urgency level
        if urgent_count >= 3 or exclamation_count >= 5:
            return UrgencyLevel.CRITICAL
        elif urgent_count >= 2 or exclamation_count >= 3 or caps_ratio > 0.5:
            return UrgencyLevel.HIGH
        elif urgent_count >= 1 or exclamation_count >= 2:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from the text"""
        # Simple extraction of important phrases
        phrases = []
        sentences = text.split('.')
        
        for sentence in sentences[:3]:  # Focus on first 3 sentences
            # Extract phrases with negative or positive keywords
            for keyword in self.NEGATIVE_KEYWORDS + self.POSITIVE_KEYWORDS:
                if keyword in sentence.lower():
                    phrases.append(sentence.strip()[:50])
                    break
        
        return phrases[:5]
    
    def _detect_emotional_indicators(self, text: str) -> List[str]:
        """Detect specific emotional indicators in the text"""
        indicators = []
        text_lower = text.lower()
        
        # Check for negative emotions
        for keyword in self.NEGATIVE_KEYWORDS:
            if keyword in text_lower:
                indicators.append(f"negative: {keyword}")
        
        # Check for positive emotions
        for keyword in self.POSITIVE_KEYWORDS:
            if keyword in text_lower:
                indicators.append(f"positive: {keyword}")
        
        # Check for questions (may indicate confusion)
        if text.count('?') >= 2:
            indicators.append("multiple questions")
        
        # Check for repeated punctuation (emotional emphasis)
        if '!!' in text or '???' in text:
            indicators.append("emotional emphasis")
        
        return indicators[:10]
    
    async def _execute(self, text: str, context: str = None) -> Dict[str, Any]:
        """
        Analyze sentiment in the provided text.
        
        Args:
            text: The customer message to analyze
            context: Optional context from conversation history
            
        Returns:
            Detailed sentiment analysis
        """
        # Calculate sentiment score
        sentiment_score = self._calculate_sentiment_score(text)
        
        # Determine sentiment level
        sentiment_level = self._calculate_sentiment_level(sentiment_score)
        
        # Detect urgency
        urgency_level = self._detect_urgency(text)
        
        # Extract key phrases
        key_phrases = self._extract_key_phrases(text)
        
        # Detect emotional indicators
        emotional_indicators = self._detect_emotional_indicators(text)
        
        # Calculate subjectivity (simplified)
        subjectivity = min(1.0, len(emotional_indicators) * 0.15)
        
        # Determine if escalation is needed
        requires_escalation = (
            sentiment_score <= self.escalation_threshold or
            urgency_level in [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH] or
            len([i for i in emotional_indicators if i.startswith("negative")]) >= 3
        )
        
        # Calculate confidence
        text_length = len(text)
        confidence = min(0.95, 0.5 + (min(text_length, 500) / 1000))
        
        # Create analysis result
        analysis = SentimentAnalysis(
            text=text[:200] + "..." if len(text) > 200 else text,
            sentiment_score=round(sentiment_score, 3),
            sentiment_level=sentiment_level,
            urgency_level=urgency_level,
            subjectivity=round(subjectivity, 3),
            key_phrases=key_phrases,
            emotional_indicators=emotional_indicators,
            requires_escalation=requires_escalation,
            confidence=round(confidence, 3)
        )
        
        return {
            "sentiment_score": analysis.sentiment_score,
            "sentiment_level": analysis.sentiment_level.value,
            "urgency_level": analysis.urgency_level.value,
            "subjectivity": analysis.subjectivity,
            "key_phrases": analysis.key_phrases,
            "emotional_indicators": analysis.emotional_indicators,
            "requires_escalation": analysis.requires_escalation,
            "confidence": analysis.confidence,
            "summary": self._generate_summary(analysis)
        }
    
    def _generate_summary(self, analysis: SentimentAnalysis) -> str:
        """Generate a human-readable summary of the analysis"""
        summary_parts = []
        
        # Sentiment summary
        if analysis.sentiment_level == SentimentLevel.VERY_NEGATIVE:
            summary_parts.append("Customer is very upset")
        elif analysis.sentiment_level == SentimentLevel.NEGATIVE:
            summary_parts.append("Customer appears frustrated")
        elif analysis.sentiment_level == SentimentLevel.POSITIVE:
            summary_parts.append("Customer seems satisfied")
        elif analysis.sentiment_level == SentimentLevel.VERY_POSITIVE:
            summary_parts.append("Customer is very happy")
        else:
            summary_parts.append("Customer sentiment is neutral")
        
        # Urgency summary
        if analysis.urgency_level in [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH]:
            summary_parts.append("requires immediate attention")
        
        # Escalation summary
        if analysis.requires_escalation:
            summary_parts.append("consider escalation to supervisor")
        
        return " - ".join(summary_parts)
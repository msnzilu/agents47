"""
tests/test_research_tools.py
Phase 6: Research Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from agents.tools.research_tools import (
    MultiSourceSearch,
    Summarizer,
    DataExtractor,
    ReportGenerator
)

User = get_user_model()


class TestMultiSourceSearch(TestCase):
    """Test multi-source search aggregates results"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        self.searcher = MultiSourceSearch(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_multi_source_search_aggregates(self):
        """Test that search aggregates results from multiple sources"""
        result = await self.searcher._execute(
            query="artificial intelligence trends",
            sources=['web', 'academic', 'news']
        )
        
        assert result['query'] == "artificial intelligence trends"
        assert len(result['sources_searched']) == 3
        assert result['total_results'] > 0
        assert 'results' in result
        
        # Verify results contain source field
        for item in result['results']:
            assert 'source' in item
            assert item['source'] in ['web', 'academic', 'news']
    
    @pytest.mark.asyncio
    async def test_search_all_sources_default(self):
        """Test searching all sources when none specified"""
        result = await self.searcher._execute(query="machine learning")
        
        assert len(result['sources_searched']) >= 3
        assert result['total_results'] > 0
    
    @pytest.mark.asyncio
    async def test_search_results_structure(self):
        """Test search result structure"""
        result = await self.searcher._execute(
            query="climate change",
            sources=['web']
        )
        
        assert isinstance(result['results'], list)
        for item in result['results']:
            assert 'source' in item
            assert 'title' in item
            assert 'url' in item
            assert 'snippet' in item


class TestSummarizer(TestCase):
    """Test summarization chain condenses text"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        self.summarizer = Summarizer(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_summarization_chain_condenses(self):
        """Test that summarization reduces text length significantly"""
        long_text = ". ".join([
            f"This is sentence number {i} containing important information"
            for i in range(100)
        ])
        
        result = await self.summarizer._execute(
            text=long_text,
            style='paragraph'
        )
        
        assert result['summary_length'] < result['original_length']
        assert 'compression_ratio' in result
        
        # Verify significant compression
        compression = result['compression_ratio']
        assert compression < 0.5  # Less than 50% of original size
    
    @pytest.mark.asyncio
    async def test_bullet_style_summary(self):
        """Test bullet point style summarization"""
        text = """
        Machine learning is a subset of artificial intelligence. 
        It enables systems to learn from data. 
        Deep learning is a more advanced form of machine learning.
        Neural networks are used in deep learning.
        """
        
        result = await self.summarizer._execute(
            text=text,
            style='bullet'
        )
        
        assert '-' in result['summary']
        assert result['summary_length'] > 0
    
    @pytest.mark.asyncio
    async def test_paragraph_style_summary(self):
        """Test paragraph style summarization"""
        text = """
        Artificial intelligence is transforming industries.
        Companies are investing heavily in AI research.
        Machine learning models are becoming more sophisticated.
        """
        
        result = await self.summarizer._execute(
            text=text,
            style='paragraph'
        )
        
        assert '-' not in result['summary']
        assert '.' in result['summary']
        assert result['original_length'] > 0


class TestDataExtractor(TestCase):
    """Test data extraction from text"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        self.extractor = DataExtractor(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_data_extraction_from_text(self):
        """Test extraction of structured data from unstructured text"""
        text = """
        Please contact us at support@example.com or sales@company.com.
        Our office is located at 123 Main Street.
        The meeting is scheduled for 12/15/2024 at 2:00 PM.
        Our budget for this project is $50000.
        Visit our website at https://example.com for more information.
        You can also check https://docs.example.com for documentation.
        """
        
        result = await self.extractor._execute(
            text=text,
            extract_types=['urls', 'dates', 'numbers']
        )
        
        data = result['extracted_data']
        
        # Test URL extraction
        assert 'urls' in data
        assert len(data['urls']) >= 2
        
        # Test date extraction
        assert 'dates' in data
        assert len(data['dates']) > 0
        
        # Test number extraction
        assert 'numbers' in data
        assert len(data['numbers']) > 0
        assert result['total_items'] > 0
    
    @pytest.mark.asyncio
    async def test_url_extraction_only(self):
        """Test extracting only URLs"""
        text = "Visit https://example.com and http://test.org for more info."
        
        result = await self.extractor._execute(
            text=text,
            extract_types=['urls']
        )
        
        urls = result['extracted_data']['urls']
        assert len(urls) >= 2
        assert 'https://example.com' in urls[0] or 'http://test.org' in urls[0]
    
    @pytest.mark.asyncio
    async def test_entity_extraction(self):
        """Test named entity extraction (proper nouns)"""
        text = "John Smith from Microsoft met with Sarah Johnson at Apple headquarters."
        
        result = await self.extractor._execute(
            text=text,
            extract_types=['entities']
        )
        
        entities = result['extracted_data']['entities']
        assert len(entities) > 0
        # Should extract capitalized names
        assert any(entity in ['John', 'Smith', 'Microsoft', 'Sarah', 'Johnson', 'Apple'] for entity in entities)
    
    @pytest.mark.asyncio
    async def test_number_extraction(self):
        """Test extraction of numbers"""
        text = "The revenue increased by 25 percent. We have 100 employees and 50 contractors."
        
        result = await self.extractor._execute(
            text=text,
            extract_types=['numbers']
        )
        
        numbers = result['extracted_data']['numbers']
        assert len(numbers) > 0
        assert '25' in numbers or '100' in numbers or '50' in numbers


class TestReportGeneration(TestCase):
    """Test report generation format (integration test)"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        self.searcher = MultiSourceSearch(agent=self.agent)
        self.summarizer = Summarizer(agent=self.agent)
        self.report_gen = ReportGenerator(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_report_generation_format(self):
        """Test combining search and summarization for report generation"""
        # Perform search
        search_result = await self.searcher._execute(
            query="renewable energy trends",
            sources=['web', 'academic']
        )
        
        # Create text from search results for summarization
        combined_text = "\n\n".join([
            f"{item.get('title', 'Result')}: {item.get('snippet', 'No content')}"
            for item in search_result['results']
        ])
        
        # Summarize the results
        summary_result = await self.summarizer._execute(
            text=combined_text,
            style='bullet'
        )
        
        # Verify report components
        assert 'summary' in summary_result
        assert 'compression_ratio' in summary_result
        assert '-' in summary_result['summary']
        
        # Verify original search data is available
        assert search_result['total_results'] > 0
        assert len(search_result['sources_searched']) > 0
    
    @pytest.mark.asyncio
    async def test_report_generator_markdown(self):
        """Test report generator with markdown format"""
        data = {
            'title': 'AI Research Report',
            'findings': [
                'Machine learning adoption is increasing',
                'Deep learning models are more accurate',
                'Natural language processing has improved'
            ]
        }
        
        result = await self.report_gen._execute(data=data, format='markdown')
        
        assert 'report' in result
        assert '# AI Research Report' in result['report']
        assert '## Key Findings' in result['report']
        assert 'Machine learning adoption' in result['report']
        assert result['format'] == 'markdown'
        assert result['word_count'] > 0
    
    @pytest.mark.asyncio
    async def test_report_generator_text(self):
        """Test report generator with text format"""
        data = {
            'title': 'Research Summary',
            'findings': [
                'Finding one',
                'Finding two'
            ]
        }
        
        result = await self.report_gen._execute(data=data, format='text')
        
        assert 'report' in result
        assert 'Research Summary' in result['report']
        assert 'Finding one' in result['report']
        assert result['format'] == 'text'
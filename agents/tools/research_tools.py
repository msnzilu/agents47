"""
Research Tools for Phase 6.
Handles multi-source search, summarization, data extraction, and report generation.
"""

import re
import logging
from typing import Dict, Any, List
from datetime import datetime

from agents.tools.base import BaseTool, tool

logger = logging.getLogger(__name__)


@tool(name="multi_source_search", use_cases=["research"])
class MultiSourceSearch(BaseTool):
    """Searches multiple sources and aggregates results."""
    
    async def _execute(self, query: str, sources: List[str] = None) -> Dict[str, Any]:
        """Search multiple sources."""
        if sources is None:
            sources = ['web', 'academic', 'news']
        
        results = [
            {
                'title': f'Result from {source} for: {query}',
                'url': f'https://example.com/{source}/{query.replace(" ", "-")}',
                'snippet': f'This is a relevant snippet about {query} from {source}.',
                'source': source,
                'date': datetime.now().isoformat()
            }
            for source in sources
        ]
        
        return {
            'query': query,
            'sources_searched': sources,
            'results': results,
            'total_results': len(results)
        }


@tool(name="summarizer", use_cases=["research"])
class Summarizer(BaseTool):
    """Summarizes long text into concise summaries."""
    
    async def _execute(self, text: str, style: str = 'paragraph') -> Dict[str, Any]:
        """Summarize text."""
        sentences = text.split('.')
        
        if style == 'bullet':
            summary = '\n'.join([f'- {s.strip()}' for s in sentences[:3] if s.strip()])
        else:
            summary = '. '.join(sentences[:3]) + '.'
        
        return {
            'summary': summary,
            'original_length': len(text),
            'summary_length': len(summary),
            'compression_ratio': len(summary) / max(len(text), 1)
        }


@tool(name="data_extractor", use_cases=["research"])
class DataExtractor(BaseTool):
    """Extracts structured data from unstructured text."""
    
    async def _execute(self, text: str, extract_types: List[str] = None) -> Dict[str, Any]:
        """Extract data from text."""
        if extract_types is None:
            extract_types = ['entities', 'dates', 'numbers']
        
        extracted = {}
        
        if 'entities' in extract_types:
            entities = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', text)
            extracted['entities'] = list(set(entities))
        
        if 'dates' in extract_types:
            dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b', text)
            extracted['dates'] = dates
        
        if 'numbers' in extract_types:
            numbers = re.findall(r'\b\d+\.?\d*\b', text)
            extracted['numbers'] = numbers
        
        if 'urls' in extract_types:
            urls = re.findall(r'https?://[^\s]+', text)
            extracted['urls'] = urls
        
        return {
            'extracted_data': extracted,
            'total_items': sum(len(v) for v in extracted.values())
        }


@tool(name="report_generator", use_cases=["research"])
class ReportGenerator(BaseTool):
    """Generates formatted research reports."""
    
    async def _execute(self, data: Dict[str, Any], format: str = 'markdown') -> Dict[str, Any]:
        """Generate a research report."""
        title = data.get('title', 'Research Report')
        findings = data.get('findings', [])
        
        if format == 'markdown':
            report = f"# {title}\n\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            report += "## Key Findings\n\n"
            for i, finding in enumerate(findings, 1):
                report += f"{i}. {finding}\n"
        else:
            report = f"{title}\n{'='*len(title)}\n\n"
            for finding in findings:
                report += f"- {finding}\n"
        
        return {
            'report': report,
            'format': format,
            'word_count': len(report.split())
        }


__all__ = [
    'MultiSourceSearch',
    'Summarizer',
    'DataExtractor',
    'ReportGenerator'
]
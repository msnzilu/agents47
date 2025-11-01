"""
Advanced RAG Service - Phase 11
Hybrid search combining vector and keyword search with reranking
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"sentence_transformers not available: {e}. Reranking will be disabled.")
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    CrossEncoder = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("openai not available. Some features will be disabled.")
    OPENAI_AVAILABLE = False
    openai = None

try:
    from elasticsearch import Elasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    logger.warning("elasticsearch not available. Keyword search will be disabled.")
    ELASTICSEARCH_AVAILABLE = False
    Elasticsearch = None


class HybridSearchService:
    """
    Service for hybrid search combining vector and keyword search
    """
    
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        self.config = getattr(knowledge_base, 'hybrid_search_config', None)
        
        # Initialize Elasticsearch if needed (Phase 11)
        self.es_client = None
        if ELASTICSEARCH_AVAILABLE and self.config and getattr(self.config, 'es_enabled', False):
            try:
                from django.conf import settings
                self.es_client = Elasticsearch(
                    hosts=[settings.ELASTICSEARCH_HOST],
                    basic_auth=(
                        settings.ELASTICSEARCH_USER, 
                        settings.ELASTICSEARCH_PASSWORD
                    )
                )
            except Exception as e:
                logger.warning(f"Elasticsearch not available: {e}")
        
        # Initialize reranker if enabled
        self.reranker = None
        if SENTENCE_TRANSFORMERS_AVAILABLE and self.config and getattr(self.config, 'rerank_enabled', False):
            try:
                rerank_model = getattr(self.config, 'rerank_model', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
                self.reranker = CrossEncoder(rerank_model)
            except Exception as e:
                logger.warning(f"Reranker not available: {e}")
    
    async def search(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search with optional reranking
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters for search
            
        Returns:
            List of search results with scores
        """
        # Step 1: Get query embedding
        query_embedding = await self._get_query_embedding(query)
        
        # Step 2: Expand query (if enabled)
        expanded_queries = await self._expand_query(query)
        
        # Step 3: Perform vector search
        rerank_top_k = getattr(self.config, 'rerank_top_k', top_k * 2) if self.config else top_k * 2
        vector_results = await self._vector_search(query_embedding, top_k=rerank_top_k)
        
        # Step 4: Perform keyword search if enabled
        keyword_results = []
        if self.es_client and self.config and getattr(self.config, 'es_enabled', False):
            keyword_results = await self._keyword_search(query, expanded_queries, top_k=rerank_top_k)
        
        # Step 5: Merge results
        vector_weight = getattr(self.config, 'vector_weight', 0.7) if self.config else 0.7
        keyword_weight = getattr(self.config, 'keyword_weight', 0.3) if self.config else 0.3
        merged_results = self._merge_results(vector_results, keyword_results, vector_weight, keyword_weight)
        
        # Step 6: Rerank if enabled
        if self.reranker and self.config and getattr(self.config, 'rerank_enabled', False):
            merged_results = await self._rerank_results(query, merged_results, top_k)
        else:
            merged_results = merged_results[:top_k]
        
        return merged_results
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query"""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available, returning empty embedding")
            return []
        
        from asgiref.sync import sync_to_async
        
        try:
            response = await sync_to_async(openai.Embedding.create)(
                input=query,
                model="text-embedding-ada-002"
            )
            return response['data'][0]['embedding']
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            return []
    
    async def _expand_query(self, query: str) -> List[str]:
        """
        Expand query with synonyms and related terms using LLM
        """
        if not OPENAI_AVAILABLE:
            return [query]
        
        from asgiref.sync import sync_to_async
        from agents.models import QueryExpansion
        
        try:
            # Check cache first
            cached = await sync_to_async(
                QueryExpansion.objects.filter(original_query=query).first
            )()
            
            if cached:
                cached.use_count += 1
                await sync_to_async(cached.save)()
                return cached.expanded_queries
        except Exception as e:
            logger.warning(f"Could not check query expansion cache: {e}")
        
        # Generate expansions using LLM
        prompt = f"""
        Generate 3-5 alternative phrasings or synonymous queries for:
        "{query}"
        
        Return only the queries, one per line, without numbers or bullets.
        """
        
        try:
            response = await sync_to_async(openai.ChatCompletion.create)(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a query expansion assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            expansions = [
                line.strip() 
                for line in response.choices[0].message.content.split('\n')
                if line.strip()
            ]
            
            # Cache for future use
            try:
                await sync_to_async(QueryExpansion.objects.create)(
                    original_query=query,
                    expanded_queries=expansions,
                    agent_id=self.knowledge_base.agent_id
                )
            except Exception as e:
                logger.warning(f"Could not cache query expansion: {e}")
            
            return expansions
            
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]
    
    async def _vector_search(
        self, 
        query_embedding: List[float], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        from asgiref.sync import sync_to_async
        from agents.models import DocumentChunk
        
        try:
            results = await sync_to_async(DocumentChunk.similarity_search)(
                agent=self.knowledge_base.agent,
                query_embedding=query_embedding,
                limit=top_k
            )
            
            return [
                {
                    **result,
                    'search_type': 'vector',
                    'vector_score': result.get('similarity', 0)
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def _keyword_search(
        self, 
        query: str,
        expanded_queries: List[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform keyword search using Elasticsearch"""
        if not self.es_client:
            return []
        
        try:
            # Build multi-match query with expansions
            should_clauses = [
                {"match": {"content": {"query": q, "boost": 1.0 if q == query else 0.5}}}
                for q in [query] + expanded_queries
            ]
            
            es_index_name = getattr(self.config, 'es_index_name', 'knowledge_base')
            search_body = {
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "filter": [
                            {"term": {"knowledge_base_id": self.knowledge_base.id}}
                        ]
                    }
                },
                "size": top_k
            }
            
            from asgiref.sync import sync_to_async
            response = await sync_to_async(self.es_client.search)(
                index=es_index_name,
                body=search_body
            )
            
            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_source']['chunk_id'],
                    'content': hit['_source']['content'],
                    'metadata': hit['_source'].get('metadata', {}),
                    'document_title': hit['_source'].get('title', ''),
                    'search_type': 'keyword',
                    'keyword_score': hit['_score']
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []
    
    def _merge_results(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        vector_weight: float,
        keyword_weight: float
    ) -> List[Dict[str, Any]]:
        """
        Merge vector and keyword results using weighted scores
        """
        # Normalize scores to 0-1 range
        def normalize_scores(results, score_key):
            if not results:
                return results
            
            scores = [r.get(score_key, 0) for r in results]
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score == min_score:
                for r in results:
                    r[f'normalized_{score_key}'] = 1.0
            else:
                for r in results:
                    r[f'normalized_{score_key}'] = (
                        (r.get(score_key, 0) - min_score) / (max_score - min_score)
                    )
            
            return results
        
        vector_results = normalize_scores(vector_results, 'vector_score')
        keyword_results = normalize_scores(keyword_results, 'keyword_score')
        
        # Merge by chunk ID
        merged = {}
        
        for result in vector_results:
            chunk_id = result.get('id')
            if chunk_id:
                merged[chunk_id] = {
                    **result,
                    'vector_score_normalized': result.get('normalized_vector_score', 0),
                    'keyword_score_normalized': 0
                }
        
        for result in keyword_results:
            chunk_id = result.get('id')
            if chunk_id:
                if chunk_id in merged:
                    merged[chunk_id]['keyword_score_normalized'] = result.get('normalized_keyword_score', 0)
                else:
                    merged[chunk_id] = {
                        **result,
                        'vector_score_normalized': 0,
                        'keyword_score_normalized': result.get('normalized_keyword_score', 0)
                    }
        
        # Calculate hybrid scores
        for chunk_id, result in merged.items():
            result['hybrid_score'] = (
                vector_weight * result['vector_score_normalized'] +
                keyword_weight * result['keyword_score_normalized']
            )
        
        # Sort by hybrid score
        merged_list = sorted(
            merged.values(),
            key=lambda x: x.get('hybrid_score', 0),
            reverse=True
        )
        
        return merged_list
    
    async def _rerank_results(
        self, 
        query: str, 
        results: List[Dict], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank results using cross-encoder model
        """
        if not self.reranker or not results:
            return results[:top_k]
        
        try:
            # Prepare pairs for reranking
            pairs = [[query, result.get('content', '')] for result in results]
            
            # Get reranking scores
            from asgiref.sync import sync_to_async
            scores = await sync_to_async(self.reranker.predict)(pairs)
            
            # Add rerank scores to results
            for result, score in zip(results, scores):
                result['rerank_score'] = float(score)
            
            # Sort by rerank score
            reranked = sorted(
                results,
                key=lambda x: x.get('rerank_score', 0),
                reverse=True
            )
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return results[:top_k]


class RetrievalAugmentationService:
    """
    Service for retrieval-augmented generation with advanced features
    """
    
    def __init__(self, agent=None, knowledge_base=None, hybrid_search_service=None):
        """
        Initialize the RAG service
        
        Args:
            agent: Agent instance (for compatibility with views)
            knowledge_base: Knowledge base instance
            hybrid_search_service: Optional hybrid search service
        """
        self.agent = agent
        self.knowledge_base = knowledge_base
        
        # If agent provided but no knowledge base, try to get first active KB
        if agent and not knowledge_base:
            try:
                from agents.models import KnowledgeBase
                self.knowledge_base = agent.knowledge_bases.filter(
                    is_active=True,
                    status='completed'
                ).first()
            except Exception as e:
                logger.warning(f"Could not load knowledge base for agent: {e}")
        
        self.hybrid_search = hybrid_search_service or (
            HybridSearchService(self.knowledge_base) if self.knowledge_base else None
        )
    
    async def retrieve_and_augment(
        self,
        query: str,
        top_k: int = 5,
        use_reranking: bool = False,
        filters: Dict = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieve relevant documents and prepare context for augmentation
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            use_reranking: Whether to use reranking
            filters: Optional filters for search
            
        Returns:
            Tuple of (augmented_prompt, sources)
            - augmented_prompt: String with context prepended to query
            - sources: List of source documents with metadata
        """
        if not self.hybrid_search:
            logger.warning("No hybrid search service available")
            return query, []
        
        try:
            # Perform hybrid search
            retrieved = await self.hybrid_search.search(
                query=query,
                top_k=top_k,
                filters=filters
            )
            
            # Build augmented context
            context = self._build_context(retrieved)
            
            # Create augmented prompt
            if context:
                augmented_prompt = f"""Context from knowledge base:

{context}

---

User Question: {query}

Please answer the question based on the context provided above. If the context doesn't contain relevant information, say so."""
            else:
                augmented_prompt = query
            
            return augmented_prompt, retrieved
            
        except Exception as e:
            logger.error(f"Retrieval and augmentation failed: {e}")
            return query, []
    
    async def retrieve_and_augment_dict(
        self,
        query: str,
        top_k: int = 5,
        use_reranking: bool = False,
        filters: Dict = None
    ) -> Dict[str, Any]:
        """
        Alternative method that returns a dictionary instead of tuple
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            use_reranking: Whether to use reranking
            filters: Optional filters for search
            
        Returns:
            Dictionary with retrieved documents and augmented context
        """
        augmented_prompt, sources = await self.retrieve_and_augment(
            query=query,
            top_k=top_k,
            use_reranking=use_reranking,
            filters=filters
        )
        
        return {
            'augmented_prompt': augmented_prompt,
            'retrieved_documents': sources,
            'context': self._build_context(sources),
            'num_retrieved': len(sources)
        }
    
    def _build_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Build context string from retrieved documents
        
        Args:
            documents: List of retrieved documents
            
        Returns:
            Formatted context string
        """
        if not documents:
            return ""
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            content = doc.get('content', '')
            source = doc.get('document_title') or doc.get('source', 'Unknown')
            score = doc.get('rerank_score') or doc.get('hybrid_score') or doc.get('vector_score', 0)
            
            context_parts.append(
                f"[Document {i}] (Source: {source}, Relevance: {score:.3f})\n{content}"
            )
        
        return "\n\n".join(context_parts)
    
    def chunk_document(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Split document into overlapping chunks
        
        Args:
            text: Document text
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.7:  # Only break if reasonably far
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - chunk_overlap
        
        return [c for c in chunks if c]  # Filter empty chunks
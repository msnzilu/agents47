"""
Service layer for knowledge base operations.
Handles document processing, chunking, and embedding generation.
"""
import logging
import tiktoken
from typing import List, Dict, Optional
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_anthropic import AnthropicEmbeddings
import PyPDF2
import docx
import csv
import json
from io import StringIO

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handle document extraction and processing."""
    
    @staticmethod
    def extract_text(file_path: str, document_type: str) -> str:
        """Extract text from various document types."""
        try:
            if document_type == 'pdf':
                return DocumentProcessor._extract_pdf(file_path)
            elif document_type == 'docx':
                return DocumentProcessor._extract_docx(file_path)
            elif document_type == 'csv':
                return DocumentProcessor._extract_csv(file_path)
            elif document_type == 'json':
                return DocumentProcessor._extract_json(file_path)
            elif document_type in ['text', 'markdown', 'html']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                raise ValueError(f"Unsupported document type: {document_type}")
        except Exception as e:
            logger.error(f"Failed to extract text: {str(e)}")
            raise
    
    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        """Extract text from PDF."""
        text = []
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text.append(page.extract_text())
        return '\n\n'.join(text)
    
    @staticmethod
    def _extract_docx(file_path: str) -> str:
        """Extract text from Word document."""
        doc = docx.Document(file_path)
        return '\n\n'.join([para.text for para in doc.paragraphs])
    
    @staticmethod
    def _extract_csv(file_path: str) -> str:
        """Extract text from CSV."""
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            rows = [', '.join(row) for row in reader]
        return '\n'.join(rows)
    
    @staticmethod
    def _extract_json(file_path: str) -> str:
        """Extract text from JSON."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return json.dumps(data, indent=2)
    
    @staticmethod
    def count_tokens(text: str, model: str = "gpt-4") -> int:
        """Count tokens in text using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except:
            # Fallback to approximate count
            return len(text) // 4


class ChunkingService:
    """Handle text chunking strategies."""
    
    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        use_case: Optional[str] = None
    ) -> List[Dict]:
        """
        Chunk text using appropriate strategy based on use case.
        """
        # Adjust chunking based on use case
        if use_case == 'support':
            # Smaller chunks for precise FAQ retrieval
            chunk_size = 500
            chunk_overlap = 100
        elif use_case == 'research':
            # Larger chunks for context
            chunk_size = 1500
            chunk_overlap = 300
        elif use_case == 'knowledge':
            # Balanced chunks
            chunk_size = 1000
            chunk_overlap = 200
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        
        # Create chunk metadata
        chunk_data = []
        for idx, chunk in enumerate(chunks):
            chunk_data.append({
                'content': chunk,
                'index': idx,
                'token_count': DocumentProcessor.count_tokens(chunk),
                'metadata': {
                    'chunk_size': chunk_size,
                    'chunk_overlap': chunk_overlap,
                    'total_chunks': len(chunks)
                }
            })
        
        return chunk_data


class EmbeddingService:
    """Handle embedding generation."""
    
    def __init__(self, provider: str = 'openai', api_key: Optional[str] = None):
        """Initialize embedding service."""
        self.provider = provider
        
        if provider == 'openai':
            self.embedder = OpenAIEmbeddings(
                model="text-embedding-ada-002",
                api_key=api_key
            )
        elif provider == 'anthropic':
            # Anthropic doesn't have embeddings, fallback to OpenAI
            self.embedder = OpenAIEmbeddings(api_key=api_key)
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            return self.embedder.embed_query(text)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            return self.embedder.embed_documents(texts)
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            raise


class KnowledgeBaseService:
    """
    Main service for knowledge base operations.
    """
    
    @staticmethod
    def process_document(knowledge_base_id: int):
        """
        Process a knowledge base document: extract, chunk, and embed.
        This should be called as a Celery task for async processing.
        """
        from .models import KnowledgeBase, DocumentChunk
        
        try:
            kb = KnowledgeBase.objects.get(id=knowledge_base_id)
            kb.status = 'processing'
            kb.save()
            
            # Extract text
            if kb.file_path:
                text = DocumentProcessor.extract_text(
                    kb.file_path.path,
                    kb.document_type
                )
                kb.content = text
                kb.file_size = len(text.encode('utf-8'))
                kb.save()
            elif not kb.content:
                raise ValueError("No content or file provided")
            
            # Chunk text
            chunks = ChunkingService.chunk_text(
                kb.content,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
                use_case=kb.agent.use_case
            )
            
            # Get embedding service
            integration = kb.agent.integrations.filter(
                integration_type__in=['openai', 'anthropic'],
                is_active=True
            ).first()
            
            if not integration:
                raise ValueError("No active LLM integration for embeddings")
            
            api_key = integration.config.get('api_key')
            embedder = EmbeddingService(
                provider=integration.integration_type,
                api_key=api_key
            )
            
            # Generate embeddings in batch
            chunk_texts = [chunk['content'] for chunk in chunks]
            embeddings = embedder.generate_embeddings_batch(chunk_texts)
            
            # Create DocumentChunk records
            chunk_objects = []
            for chunk_data, embedding in zip(chunks, embeddings):
                chunk_objects.append(DocumentChunk(
                    knowledge_base=kb,
                    content=chunk_data['content'],
                    embedding=embedding,
                    chunk_index=chunk_data['index'],
                    token_count=chunk_data['token_count'],
                    metadata=chunk_data['metadata']
                ))
            
            # Bulk create chunks
            DocumentChunk.objects.bulk_create(chunk_objects)
            
            # Update knowledge base
            kb.total_chunks = len(chunk_objects)
            kb.status = 'completed'
            kb.processed_at = timezone.now()
            kb.save()
            
            logger.info(f"Successfully processed KB {kb.id}: {kb.total_chunks} chunks")
            
        except Exception as e:
            logger.error(f"Failed to process KB {knowledge_base_id}: {str(e)}")
            kb.status = 'failed'
            kb.processing_error = str(e)
            kb.save()
            raise
    
    @staticmethod
    def search_knowledge_base(
        agent,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        Search knowledge base for relevant chunks.
        """
        from .models import DocumentChunk
        
        try:
            # Get embedding service
            integration = agent.integrations.filter(
                integration_type__in=['openai', 'anthropic'],
                is_active=True
            ).first()
            
            if not integration:
                return []
            
            api_key = integration.config.get('api_key')
            embedder = EmbeddingService(
                provider=integration.integration_type,
                api_key=api_key
            )
            
            # Generate query embedding
            query_embedding = embedder.generate_embedding(query)
            
            # Search for similar chunks
            results = DocumentChunk.similarity_search(
                agent=agent,
                query_embedding=query_embedding,
                limit=limit
            )
            
            # Filter by similarity threshold
            filtered_results = [
                r for r in results
                if r['similarity'] >= similarity_threshold
            ]
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {str(e)}")
            return []
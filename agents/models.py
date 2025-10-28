"""
Agent models for AI agent configuration and management.
Phase 1: Foundation & Authentication (Skeleton)
Phase 2: Complete implementation
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField



class Agent(models.Model):
    """
    AI Agent model storing configuration and settings.
    """
    
    class UseCase(models.TextChoices):
        SUPPORT = 'support', _('Customer Support')
        RESEARCH = 'research', _('Research & Analysis')
        AUTOMATION = 'automation', _('Workflow Automation')
        SCHEDULING = 'scheduling', _('Smart Scheduling')
        KNOWLEDGE = 'knowledge', _('Knowledge Management')
        SALES = 'sales', _('Sales & Lead Generation')
    
    # Basic Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agents',
        help_text=_('Owner of this agent')
    )
    
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Display name for the agent')
    )
    
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Brief description of agent purpose')
    )
    
    use_case = models.CharField(
        _('use case'),
        max_length=20,
        choices=UseCase.choices,
        default=UseCase.SUPPORT,
        help_text=_('Primary use case for this agent')
    )
    
    # AI Configuration (Phase 3)
    prompt_template = models.TextField(
        _('prompt template'),
        blank=True,
        default='',
        help_text=_('System prompt template for the agent')
    )
    
    config_json = models.JSONField(
        _('configuration'),
        default=dict,
        blank=True,
        help_text=_('LLM and tool configuration (provider, model, temperature, etc.)')
    )
    
    # Integration Configuration (Phase 7)
    integration_hooks = models.JSONField(
        _('integration hooks'),
        default=dict,
        blank=True,
        help_text=_('Webhook URLs, API keys, channel configs for integrations')
    )
    
    # Status
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this agent is active and available for use')
    )
    enabled_tools = models.JSONField(
        default=list,
        blank=True,
        help_text='List of enabled tool names for this agent'
    )
    
    tools_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Tool-specific configuration settings'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_tools(self):
        """Get tool instances for this agent based on use case"""
        from agents.tools.base import ToolRegistry
        
        # Auto-enable tools based on use case
        if not self.enabled_tools:
            tools = ToolRegistry.get_tools_for_use_case(self.use_case)
            return tools
        
        # Or use manually selected tools
        tools = []
        for tool_name in self.enabled_tools:
            tool = ToolRegistry.create_tool(
                tool_name, 
                agent=self,
                **self.tools_config.get(tool_name, {})
            )
            if tool:
                tools.append(tool)
        return tools

    def can_user_chat(self, user):
        """
        Check if a user has permission to chat with this agent.
        Override this method to implement custom permission logic.
        """
        # Basic implementation - agent must be active and belong to the user
        if not self.is_active:
            return False
        
        # If agent is owned by the user, they can chat
        if self.user == user:
            return True
        
        # Add additional logic here as needed:
        # - Check if agent is public
        # - Check team permissions
        # - Check subscription status
        # etc.
        
        return False
    
    def can_user_embed(self, origin=None):
        """
        Check if embedding is allowed for this agent.
        Optionally validate the origin domain.
        """
        # Must be active
        if not self.is_active:
            return False
        
        # Add logic for allowed origins/domains
        # For now, allow if agent is active
        return True
    
    class Meta:
        verbose_name = _('agent')
        verbose_name_plural = _('agents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['use_case']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_use_case_display()})"
    
    def get_default_config(self):
        """Return default configuration based on use case."""
        defaults = {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'temperature': 0.7,
            'max_tokens': 1000,
            'tools_enabled': True,
        }
        return {**defaults, **self.config_json}
    
    def get_conversation_count(self):
        """Return number of conversations for this agent."""
        return self.conversations.count()


class KnowledgeBase(models.Model):
    """
    Knowledge base document with vector embeddings.
    Supports multiple document types and chunking strategies.
    """
    
    class DocumentType(models.TextChoices):
        TEXT = 'text', _('Plain Text')
        PDF = 'pdf', _('PDF Document')
        DOCX = 'docx', _('Word Document')
        CSV = 'csv', _('CSV File')
        JSON = 'json', _('JSON Data')
        HTML = 'html', _('HTML Content')
        MARKDOWN = 'markdown', _('Markdown')
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending Processing')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
    
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='knowledge_bases'
    )
    
    # Document info
    title = models.CharField(
        _('title'),
        max_length=255,
        help_text=_('Document title or filename')
    )
    
    document_type = models.CharField(
        _('document type'),
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.TEXT
    )
    
    file_path = models.FileField(
        _('file'),
        upload_to='knowledge/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text=_('Uploaded document file')
    )
    
    content = models.TextField(
        _('content'),
        blank=True,
        help_text=_('Extracted or raw text content')
    )
    
    # Processing status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    processing_error = models.TextField(
        _('processing error'),
        blank=True,
        help_text=_('Error message if processing failed')
    )
    
    # Document metadata
    file_size = models.IntegerField(
        _('file size'),
        blank=True,
        null=True,
        help_text=_('File size in bytes')
    )
    
    file_hash = models.CharField(
        _('file hash'),
        max_length=64,
        blank=True,
        help_text=_('SHA-256 hash for deduplication')
    )
    
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional document metadata (author, date, etc.)')
    )
    
    # Chunking configuration
    chunk_size = models.IntegerField(
        _('chunk size'),
        default=1000,
        help_text=_('Size of text chunks for embedding')
    )
    
    chunk_overlap = models.IntegerField(
        _('chunk overlap'),
        default=200,
        help_text=_('Overlap between chunks')
    )
    
    # Statistics
    total_chunks = models.IntegerField(
        _('total chunks'),
        default=0,
        help_text=_('Number of chunks created')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(
        _('processed at'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('knowledge base')
        verbose_name_plural = _('knowledge bases')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['file_hash']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.agent.name}"
    
    def calculate_hash(self):
        """Calculate SHA-256 hash of content."""
        if self.content:
            return hashlib.sha256(self.content.encode()).hexdigest()
        return ''
    
    def save(self, *args, **kwargs):
        if self.content and not self.file_hash:
            self.file_hash = self.calculate_hash()
        super().save(*args, **kwargs)


class DocumentChunk(models.Model):
    """
    Individual chunk of a knowledge base document with vector embedding.
    """
    
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    
    # Chunk content
    content = models.TextField(
        _('content'),
        help_text=_('Text content of this chunk')
    )
    
    # Vector embedding (1536 dimensions for OpenAI text-embedding-ada-002)
    embedding = VectorField(
        dimensions=1536,
        blank=True,
        null=True
    )
    
    # Chunk metadata
    chunk_index = models.IntegerField(
        _('chunk index'),
        help_text=_('Position of this chunk in the document')
    )
    
    token_count = models.IntegerField(
        _('token count'),
        default=0,
        help_text=_('Approximate token count')
    )
    
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Chunk-specific metadata (page number, section, etc.)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('document chunk')
        verbose_name_plural = _('document chunks')
        ordering = ['knowledge_base', 'chunk_index']
        indexes = [
            models.Index(fields=['knowledge_base', 'chunk_index']),
        ]
        # Add vector index for similarity search
        # This will be created via migration
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.knowledge_base.title}"
    
    @classmethod
    def similarity_search(cls, agent, query_embedding, limit=5):
        """
        Perform cosine similarity search for relevant chunks.
        """
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT dc.id, dc.content, dc.metadata, dc.chunk_index, kb.title,
                       1 - (dc.embedding <=> %s::vector) as similarity
                FROM agents_documentchunk dc
                JOIN agents_knowledgebase kb ON dc.knowledge_base_id = kb.id
                WHERE kb.agent_id = %s AND dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
            """, [query_embedding, agent.id, query_embedding, limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'content': row[1],
                    'metadata': row[2],
                    'chunk_index': row[3],
                    'document_title': row[4],
                    'similarity': float(row[5])
                })
            
            return results


class ToolExecution(models.Model):
    """Tool execution tracking (from Phase 3-4)"""
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='tool_executions')
    tool_name = models.CharField(max_length=100)
    input_data = models.JSONField(default=dict)
    output_data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tool_name} - {self.created_at}"
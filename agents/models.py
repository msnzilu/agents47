"""
Agent models for AI agent configuration and management.
Phase 1: Foundation & Authentication (Skeleton)
Phase 2: Complete implementation
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField
from django.core.validators import MinValueValidator, MaxValueValidator


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
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this knowledge base is active')
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
            models.Index(fields=['agent', 'is_active']),
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


class AgentOrchestration(models.Model):
    """
    Configuration for multi-agent workflows
    """
    
    class OrchestrationStrategy(models.TextChoices):
        SEQUENTIAL = 'sequential', _('Sequential')
        PARALLEL = 'parallel', _('Parallel')
        CONDITIONAL = 'conditional', _('Conditional')
        HIERARCHICAL = 'hierarchical', _('Hierarchical')
    
    name = models.CharField(
        max_length=255,
        help_text='Name of orchestration workflow'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orchestrations'
    )
    
    orchestrator_agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='orchestrations_as_orchestrator',
        help_text='Main agent that coordinates workflow'
    )
    
    strategy = models.CharField(
        max_length=20,
        choices=OrchestrationStrategy.choices,
        default=OrchestrationStrategy.SEQUENTIAL
    )
    
    # Workflow configuration
    workflow_config = models.JSONField(
        default=dict,
        help_text='''
        {
            "steps": [
                {
                    "agent_id": 1,
                    "condition": "always|if_needed",
                    "inputs": ["query", "previous_output"],
                    "timeout_seconds": 30
                }
            ],
            "synthesis_strategy": "concatenate|summarize|vote",
            "max_parallel_agents": 3
        }
        '''
    )
    
    # Participating agents
    participant_agents = models.ManyToManyField(
        'Agent',
        related_name='orchestrations_as_participant',
        through='OrchestrationParticipant'
    )
    
    is_active = models.BooleanField(default=True)
    
    # Statistics
    total_executions = models.IntegerField(default=0)
    successful_executions = models.IntegerField(default=0)
    average_execution_time_ms = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Agent Orchestration'
        verbose_name_plural = 'Agent Orchestrations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['orchestrator_agent']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_strategy_display()})"
    
    def validate_workflow(self):
        """Validate workflow configuration"""
        errors = []
        
        # Check circular dependencies
        if self._has_circular_dependency():
            errors.append("Circular dependency detected in workflow")
        
        # Validate agent references
        agent_ids = [step['agent_id'] for step in self.workflow_config.get('steps', [])]
        valid_agents = self.participant_agents.filter(id__in=agent_ids)
        if len(agent_ids) != valid_agents.count():
            errors.append("Invalid agent references in workflow")
        
        return errors
    
    def _has_circular_dependency(self):
        """Check for circular dependencies in workflow"""
        # Implementation of cycle detection in directed graph
        visited = set()
        rec_stack = set()
        
        def is_cyclic_util(agent_id):
            visited.add(agent_id)
            rec_stack.add(agent_id)
            
            # Get dependent agents
            for step in self.workflow_config.get('steps', []):
                if step['agent_id'] == agent_id:
                    for dep_id in step.get('depends_on', []):
                        if dep_id not in visited:
                            if is_cyclic_util(dep_id):
                                return True
                        elif dep_id in rec_stack:
                            return True
            
            rec_stack.remove(agent_id)
            return False
        
        agent_ids = [step['agent_id'] for step in self.workflow_config.get('steps', [])]
        for agent_id in agent_ids:
            if agent_id not in visited:
                if is_cyclic_util(agent_id):
                    return True
        
        return False


class OrchestrationParticipant(models.Model):
    """
    Through model for agent participation in orchestrations
    """
    orchestration = models.ForeignKey(
        AgentOrchestration,
        on_delete=models.CASCADE
    )
    
    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE
    )
    
    role = models.CharField(
        max_length=50,
        help_text='Role of agent in orchestration (e.g., researcher, validator)'
    )
    
    execution_order = models.IntegerField(
        default=0,
        help_text='Order in sequential execution (0 for parallel)'
    )
    
    is_optional = models.BooleanField(
        default=False,
        help_text='Whether agent execution is optional'
    )
    
    class Meta:
        unique_together = ['orchestration', 'agent']
        ordering = ['execution_order']


class OrchestrationExecution(models.Model):
    """
    Track execution of multi-agent orchestrations
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        RUNNING = 'running', _('Running')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    orchestration = models.ForeignKey(
        AgentOrchestration,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    conversation = models.ForeignKey(
        'chat.Conversation',
        on_delete=models.CASCADE,
        related_name='orchestration_executions',
        null=True,
        blank=True
    )
    
    user_query = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Execution flow
    execution_graph = models.JSONField(
        default=dict,
        help_text='DAG of agent executions with inputs/outputs'
    )
    
    # Results
    final_response = models.TextField(blank=True)
    
    agent_outputs = models.JSONField(
        default=dict,
        help_text='Individual agent outputs keyed by agent_id'
    )
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    failed_agent_id = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['orchestration', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Execution {self.id} - {self.status}"


class AgentCommunication(models.Model):
    """
    Message passing between agents in orchestration
    """
    execution = models.ForeignKey(
        OrchestrationExecution,
        on_delete=models.CASCADE,
        related_name='communications'
    )
    
    from_agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='sent_communications'
    )
    
    to_agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='received_communications'
    )
    
    message_type = models.CharField(
        max_length=50,
        choices=[
            ('query', 'Query'),
            ('response', 'Response'),
            ('feedback', 'Feedback'),
            ('handoff', 'Handoff'),
        ]
    )
    
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']


# Phase 11: Advanced RAG Models
# Add these to the bottom of agents/models.py

class HybridSearchConfig(models.Model):
    """
    Configuration for hybrid search (vector + keyword)
    Phase 11 feature
    """
    knowledge_base = models.OneToOneField(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='hybrid_search_config'
    )
    
    # Search weights
    vector_weight = models.FloatField(
        default=0.7,
        help_text='Weight for vector similarity (0-1)'
    )
    
    keyword_weight = models.FloatField(
        default=0.3,
        help_text='Weight for keyword matching (0-1)'
    )
    
    # Reranking
    rerank_enabled = models.BooleanField(
        default=True,
        help_text='Enable reranking of search results'
    )
    
    rerank_model = models.CharField(
        max_length=100,
        default='cross-encoder/ms-marco-MiniLM-L-6-v2',
        help_text='Model for reranking'
    )
    
    rerank_top_k = models.IntegerField(
        default=20,
        help_text='Number of results to rerank'
    )
    
    # Elasticsearch settings
    es_index_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Elasticsearch index name'
    )
    
    es_enabled = models.BooleanField(
        default=False,
        help_text='Enable Elasticsearch for keyword search'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Hybrid Search Configuration'
    
    def __str__(self):
        return f"Hybrid Search: {self.knowledge_base.title}"
    
    def save(self, *args, **kwargs):
        # Validate weights sum to 1.0
        if abs((self.vector_weight + self.keyword_weight) - 1.0) > 0.01:
            raise ValueError("Vector and keyword weights must sum to 1.0")
        
        # Generate ES index name if not set
        if not self.es_index_name:
            self.es_index_name = f"kb_{self.knowledge_base.id}"
        
        super().save(*args, **kwargs)


class QueryExpansion(models.Model):
    """
    Store query expansions for better retrieval
    Phase 11 feature
    """
    original_query = models.TextField()
    expanded_queries = models.JSONField(
        default=list,
        help_text='List of expanded/synonymous queries'
    )
    
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='query_expansions',
        null=True,
        blank=True
    )
    
    # Cache for performance
    use_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['original_query']),
            models.Index(fields=['agent', 'use_count']),
        ]
    
    def __str__(self):
        return f"Query expansion: {self.original_query[:50]}"
    

# Agent Marketplace Models - Phase 11
# Add these to the bottom of agents/models.py

class MarketplaceAgent(models.Model):
    """
    Published agents available in the marketplace
    Phase 11 Feature - Agent Marketplace
    """
    
    class Category(models.TextChoices):
        SUPPORT = 'support', _('Customer Support')
        RESEARCH = 'research', _('Research & Analysis')
        SALES = 'sales', _('Sales & Marketing')
        PRODUCTIVITY = 'productivity', _('Productivity')
        CREATIVE = 'creative', _('Creative & Content')
        FINANCE = 'finance', _('Finance & Accounting')
        HR = 'hr', _('HR & Recruitment')
        EDUCATION = 'education', _('Education & Training')
        OTHER = 'other', _('Other')
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending Review')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        DRAFT = 'draft', _('Draft')
    
    # Agent Reference
    agent = models.OneToOneField(
        Agent,
        on_delete=models.CASCADE,
        related_name='marketplace_listing'
    )
    
    # Publishing User
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='published_agents'
    )
    
    # Marketplace Info
    name = models.CharField(
        max_length=255,
        help_text='Public name for marketplace'
    )
    
    tagline = models.CharField(
        max_length=200,
        help_text='Short description (one-liner)'
    )
    
    description = models.TextField(
        help_text='Detailed description'
    )
    
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    
    tags = models.JSONField(
        default=list,
        help_text='List of tags for search'
    )
    
    # Media
    logo_url = models.URLField(
        blank=True,
        help_text='Logo image URL'
    )
    
    screenshots = models.JSONField(
        default=list,
        blank=True,
        help_text='List of screenshot URLs'
    )
    
    demo_video_url = models.URLField(
        blank=True,
        help_text='YouTube or Vimeo URL'
    )
    
    # Pricing
    is_free = models.BooleanField(default=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Price in USD'
    )
    
    # Stats
    install_count = models.IntegerField(default=0)
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )
    rating_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text='Featured on marketplace homepage'
    )
    
    # Additional Info
    documentation_url = models.URLField(blank=True)
    support_url = models.URLField(blank=True)
    changelog = models.TextField(blank=True)
    version = models.CharField(max_length=20, default='1.0.0')
    
    # Requirements
    required_integrations = models.JSONField(
        default=list,
        help_text='List of required integration types'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Marketplace Agent'
        verbose_name_plural = 'Marketplace Agents'
        ordering = ['-is_featured', '-install_count', '-created_at']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['is_featured', '-install_count']),
            models.Index(fields=['publisher']),
            models.Index(fields=['-rating_average', '-install_count']),
        ]
    
    def __str__(self):
        return self.name
    
    def increment_installs(self):
        """Increment install count"""
        self.install_count += 1
        self.save(update_fields=['install_count'])
    
    def increment_views(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def update_rating(self, new_rating):
        """Update average rating with new rating"""
        if self.rating_count == 0:
            self.rating_average = new_rating
        else:
            total = (self.rating_average * self.rating_count) + new_rating
            self.rating_count += 1
            self.rating_average = total / self.rating_count
        self.save(update_fields=['rating_average', 'rating_count'])
    
    def get_rating_distribution(self):
        """Get distribution of ratings"""
        from django.db.models import Count
        return self.reviews.values('rating').annotate(count=Count('id')).order_by('-rating')


class AgentInstallation(models.Model):
    """
    Track user installations of marketplace agents
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_installations'
    )
    
    marketplace_agent = models.ForeignKey(
        MarketplaceAgent,
        on_delete=models.CASCADE,
        related_name='installations'
    )
    
    # Cloned agent instance
    installed_agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='installation_source'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    installed_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    uninstalled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'marketplace_agent']
        ordering = ['-installed_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['marketplace_agent']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.marketplace_agent.name}"
    
    def uninstall(self):
        """Mark as uninstalled"""
        from django.utils import timezone
        self.is_active = False
        self.uninstalled_at = timezone.now()
        self.save()


class AgentReview(models.Model):
    """
    User reviews for marketplace agents
    """
    marketplace_agent = models.ForeignKey(
        MarketplaceAgent,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_reviews'
    )
    
    installation = models.ForeignKey(
        AgentInstallation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review'
    )
    
    rating = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )
    
    title = models.CharField(max_length=200)
    review_text = models.TextField()
    
    # Helpful votes
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)
    
    # Publisher response
    publisher_response = models.TextField(blank=True)
    publisher_response_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_verified = models.BooleanField(
        default=False,
        help_text='User has actually installed the agent'
    )
    
    is_approved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['marketplace_agent', 'user']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['marketplace_agent', '-helpful_count']),
            models.Index(fields=['marketplace_agent', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.marketplace_agent.name} ({self.rating}★)"
    
    def save(self, *args, **kwargs):
        # Check if user has installed the agent
        if self.installation:
            self.is_verified = True
        super().save(*args, **kwargs)


class ReviewHelpfulness(models.Model):
    """
    Track user votes on review helpfulness
    """
    review = models.ForeignKey(
        AgentReview,
        on_delete=models.CASCADE,
        related_name='helpfulness_votes'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['review', 'user']
        verbose_name_plural = 'Review Helpfulness Votes'



# Custom Tool Builder Models - Phase 11
# Add these to agents/models.py

class CustomTool(models.Model):
    """
    User-created custom tools without coding
    Phase 11 Feature - No-Code Tool Builder
    """
    
    class ToolType(models.TextChoices):
        API = 'api', _('API Call')
        WEBHOOK = 'webhook', _('Webhook')
        DATABASE = 'database', _('Database Query')
        SCRIPT = 'script', _('Python Script')
        HTTP = 'http', _('HTTP Request')
    
    class AuthType(models.TextChoices):
        NONE = 'none', _('No Authentication')
        API_KEY = 'api_key', _('API Key')
        BEARER = 'bearer', _('Bearer Token')
        BASIC = 'basic', _('Basic Auth')
        OAUTH2 = 'oauth2', _('OAuth 2.0')
        CUSTOM = 'custom', _('Custom Headers')
    
    class HttpMethod(models.TextChoices):
        GET = 'GET', _('GET')
        POST = 'POST', _('POST')
        PUT = 'PUT', _('PUT')
        PATCH = 'PATCH', _('PATCH')
        DELETE = 'DELETE', _('DELETE')
    
    # Basic Info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='custom_tools'
    )
    
    name = models.CharField(
        max_length=255,
        help_text='Tool name (e.g., "Get Weather Data")'
    )
    
    slug = models.SlugField(
        max_length=255,
        help_text='Unique identifier (auto-generated)'
    )
    
    description = models.TextField(
        help_text='What this tool does'
    )
    
    tool_type = models.CharField(
        max_length=20,
        choices=ToolType.choices,
        default=ToolType.API
    )
    
    # Icon/Visual
    icon = models.CharField(
        max_length=50,
        default='🔧',
        help_text='Emoji or icon identifier'
    )
    
    # API Configuration
    endpoint_url = models.URLField(
        max_length=500,
        help_text='API endpoint URL'
    )
    
    http_method = models.CharField(
        max_length=10,
        choices=HttpMethod.choices,
        default=HttpMethod.GET
    )
    
    # Authentication
    auth_type = models.CharField(
        max_length=20,
        choices=AuthType.choices,
        default=AuthType.NONE
    )
    
    auth_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Authentication configuration (encrypted)'
    )
    
    # Headers
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text='Custom headers as key-value pairs'
    )
    
    # Parameters
    parameters = models.JSONField(
        default=list,
        help_text='List of input parameters with types and descriptions'
    )
    
    # Request Body Template
    request_body_template = models.TextField(
        blank=True,
        help_text='JSON template for request body with {{parameter}} placeholders'
    )
    
    # Response Handling
    response_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text='Map response fields to output format'
    )
    
    success_response_path = models.CharField(
        max_length=255,
        blank=True,
        help_text='JSON path to success data (e.g., "data.results")'
    )
    
    error_response_path = models.CharField(
        max_length=255,
        blank=True,
        help_text='JSON path to error message'
    )
    
    # Testing
    test_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Sample parameters for testing'
    )
    
    last_test_result = models.JSONField(
        default=dict,
        blank=True,
        help_text='Result of last test execution'
    )
    
    last_test_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Usage Stats
    execution_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=False,
        help_text='Allow other users to use this tool'
    )
    
    # Metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text='Tags for categorization'
    )
    
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text='Tool category'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'slug']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['tool_type', 'is_public']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return f"{self.icon} {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def execute(self, parameters):
        """Execute the custom tool with given parameters"""
        import requests
        import json
        from string import Template
        
        try:
            # Prepare URL with parameter substitution
            url = self.endpoint_url
            for key, value in parameters.items():
                url = url.replace(f"{{{{{key}}}}}", str(value))
            
            # Prepare headers
            headers = self.headers.copy()
            
            # Add authentication
            if self.auth_type == 'api_key':
                key = self.auth_config.get('key', 'X-API-Key')
                value = self.auth_config.get('value', '')
                headers[key] = value
            elif self.auth_type == 'bearer':
                token = self.auth_config.get('token', '')
                headers['Authorization'] = f'Bearer {token}'
            elif self.auth_type == 'basic':
                import base64
                username = self.auth_config.get('username', '')
                password = self.auth_config.get('password', '')
                credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
            
            # Prepare request body
            data = None
            if self.request_body_template and self.http_method in ['POST', 'PUT', 'PATCH']:
                template = Template(self.request_body_template)
                body_str = template.safe_substitute(parameters)
                data = json.loads(body_str)
            
            # Make request
            response = requests.request(
                method=self.http_method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=parameters if self.http_method == 'GET' else None,
                timeout=30
            )
            
            # Update stats
            self.execution_count += 1
            if response.status_code < 400:
                self.success_count += 1
            else:
                self.error_count += 1
            self.save(update_fields=['execution_count', 'success_count', 'error_count'])
            
            # Parse response
            result = {
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            self.save(update_fields=['error_count'])
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_execution(self):
        """Test the tool with test parameters"""
        from django.utils import timezone
        
        result = self.execute(self.test_parameters)
        self.last_test_result = result
        self.last_test_at = timezone.now()
        self.save(update_fields=['last_test_result', 'last_test_at'])
        
        return result


class ToolParameter(models.Model):
    """
    Parameter definition for custom tools
    """
    
    class ParameterType(models.TextChoices):
        STRING = 'string', _('String')
        INTEGER = 'integer', _('Integer')
        FLOAT = 'float', _('Float')
        BOOLEAN = 'boolean', _('Boolean')
        ARRAY = 'array', _('Array')
        OBJECT = 'object', _('Object')
        DATE = 'date', _('Date')
        DATETIME = 'datetime', _('DateTime')
        FILE = 'file', _('File')
    
    custom_tool = models.ForeignKey(
        CustomTool,
        on_delete=models.CASCADE,
        related_name='parameter_definitions'
    )
    
    name = models.CharField(max_length=100)
    
    parameter_type = models.CharField(
        max_length=20,
        choices=ParameterType.choices,
        default=ParameterType.STRING
    )
    
    description = models.TextField(
        help_text='What this parameter does'
    )
    
    is_required = models.BooleanField(default=True)
    
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Default value if not provided'
    )
    
    validation_regex = models.CharField(
        max_length=255,
        blank=True,
        help_text='Regex pattern for validation'
    )
    
    enum_values = models.JSONField(
        default=list,
        blank=True,
        help_text='List of allowed values'
    )
    
    min_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Minimum value (for numbers)'
    )
    
    max_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Maximum value (for numbers)'
    )
    
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'name']
        unique_together = ['custom_tool', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.parameter_type})"


class ToolExecution(models.Model):
    """
    Log of custom tool executions
    """
    custom_tool = models.ForeignKey(
        CustomTool,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='executions'
    )
    
    agent = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tool_executions'
    )
    
    conversation = models.ForeignKey(
        'chat.Conversation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tool_executions'
    )
    
    input_parameters = models.JSONField(null=True, blank=True)
    
    output_data = models.JSONField()
    
    status_code = models.IntegerField(null=True)
    
    execution_time_ms = models.IntegerField(null=True, blank=True,
        help_text='Execution time in milliseconds'
    )
    
    success = models.BooleanField(null=True, blank=True)
    
    error_message = models.TextField(blank=True)
    
    executed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['custom_tool', '-executed_at']),
            models.Index(fields=['agent', '-executed_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.custom_tool.name} - {self.executed_at}"
"""
Agent views for CRUD operations.
Phase 2: Complete implementation with forms and filtering
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.db.models import Count, Q
from .models import Agent, KnowledgeBase
from .forms import AgentCreateForm, AgentUpdateForm, AgentCloneForm
from chat.models import Conversation
from .tasks import process_knowledge_base_task
import logging

logger = logging.getLogger(__name__)


class AgentListView(LoginRequiredMixin, ListView):
    """
    List all agents for the current user with filtering.
    """
    model = Agent
    template_name = 'users/agents/agent_list.html'
    context_object_name = 'agents'
    paginate_by = 12
    
    def get_queryset(self):
        """Return filtered agents for current user."""
        queryset = Agent.objects.filter(user=self.request.user).annotate(
            conversation_count=Count('conversations')
        ).order_by('-created_at')
        
        # Filter by use case
        use_case = self.request.GET.get('use_case')
        if use_case:
            queryset = queryset.filter(use_case=use_case)
        
        # Filter by active status
        is_active = self.request.GET.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter values to context
        context['use_case'] = self.request.GET.get('use_case', '')
        context['is_active'] = self.request.GET.get('is_active', '')
        context['search'] = self.request.GET.get('search', '')
        
        # Add use case choices for filter dropdown
        context['use_cases'] = Agent.UseCase.choices
        
        # Stats for the user
        user_agents = Agent.objects.filter(user=self.request.user)
        context['total_agents'] = user_agents.count()
        context['active_agents'] = user_agents.filter(is_active=True).count()
        
        return context
    
class AgentDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a single agent.
    Phase 1-7: Complete implementation with stats, KB, webhooks, and embed code
    """
    model = Agent
    template_name = 'users/agents/agent_detail.html'
    context_object_name = 'agent'
    
    def get_queryset(self):
        """Ensure user can only view their own agents."""
        return Agent.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        
        # Get recent conversations with message count
        context['recent_conversations'] = Conversation.objects.filter(
            agent=agent
        ).annotate(
            message_count=Count('messages')
        ).order_by('-updated_at')[:10]
        
        # Get conversation stats
        context['total_conversations'] = agent.conversations.count()
        context['total_messages'] = agent.conversations.aggregate(
            total=Count('messages')
        )['total'] or 0
        
        # Phase 5: Knowledge Base stats
        from agents.models import KnowledgeBase
        kb_documents = KnowledgeBase.objects.filter(agent=agent)
        context['kb_total_docs'] = kb_documents.count()
        context['kb_completed_docs'] = kb_documents.filter(status='completed').count()
        context['kb_total_chunks'] = sum(
            doc.total_chunks for doc in kb_documents if doc.total_chunks
        )
        context['kb_status'] = {
            'rag_enabled': context['kb_completed_docs'] > 0,
        }
        
        # Phase 7: Webhooks count
        from webhooks.models import Webhook
        context['webhooks'] = Webhook.objects.filter(
            agent=agent, 
            is_active=True
        )
        
        # Phase 7: Generate embed code for the widget
        base_url = f"{self.request.scheme}://{self.request.get_host()}"
        context['embed_code'] = f'''<script src="{base_url}/embed/loader/{agent.id}/" async></script>
<script>
  window.AIAgentWidget = {{
    agentId: '{agent.id}',
    theme: 'light',              // 'light' or 'dark'
    primaryColor: '#4F46E5',     // Any hex color
    position: 'right',           // 'left' or 'right'
    greeting: 'Hi! Need help?'   // Custom greeting message
  }};
</script>'''
        
        return context


# class AgentDetailView(LoginRequiredMixin, DetailView):
#     """
#     Detailed view of a single agent.
#     """
#     model = Agent
#     template_name = 'users/agents/agent_detail.html'
#     context_object_name = 'agent'
    
#     def get_queryset(self):
#         """Ensure user can only view their own agents."""
#         return Agent.objects.filter(user=self.request.user)
    
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         agent = self.get_object()
        
#         # Get recent conversations
#         context['recent_conversations'] = Conversation.objects.filter(
#             agent=agent
#         ).annotate(
#             message_count=Count('messages')
#         ).order_by('-updated_at')[:10]
        
#         # Get conversation stats
#         context['total_conversations'] = agent.conversations.count()
#         context['total_messages'] = agent.conversations.aggregate(
#             total=Count('messages')
#         )['total'] or 0
        
#         return context


class AgentCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new agent.
    """
    model = Agent
    form_class = AgentCreateForm
    template_name = 'users/agents/agent_form.html'
    success_url = reverse_lazy('agents:agent_list')
    
    def form_valid(self, form):
        """Set the user before saving."""
        form.instance.user = self.request.user
        messages.success(self.request, f'Agent "{form.instance.name}" created successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Agent'
        context['button_text'] = 'Create Agent'
        return context


class AgentUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update an existing agent.
    """
    model = Agent
    form_class = AgentUpdateForm
    template_name = 'users/agents/agent_form.html'
    
    def get_queryset(self):
        """Ensure user can only update their own agents."""
        return Agent.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Agent "{form.instance.name}" updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit {self.object.name}'
        context['button_text'] = 'Save Changes'
        return context


class AgentDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete an agent.
    """
    model = Agent
    template_name = 'users/agents/agent_confirm_delete.html'
    success_url = reverse_lazy('agents:agent_list')
    
    def get_queryset(self):
        """Ensure user can only delete their own agents."""
        return Agent.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        agent_name = self.get_object().name
        messages.success(request, f'Agent "{agent_name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)


@login_required
def agent_clone(request, pk):
    """
    Clone an existing agent.
    """
    original_agent = get_object_or_404(Agent, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AgentCloneForm(request.POST)
        if form.is_valid():
            new_name = form.cleaned_data['new_name']
            include_knowledge = form.cleaned_data['include_knowledge']
            
            # Clone the agent
            new_agent = Agent.objects.create(
                user=request.user,
                name=new_name,
                description=original_agent.description,
                use_case=original_agent.use_case,
                prompt_template=original_agent.prompt_template,
                config_json=original_agent.config_json.copy(),
                integration_hooks=original_agent.integration_hooks.copy() if original_agent.integration_hooks else {},
                is_active=True,
            )
            
            # Clone knowledge base if requested
            if include_knowledge:
                from .models import KnowledgeBase
                for kb in original_agent.knowledge_bases.all():
                    KnowledgeBase.objects.create(
                        agent=new_agent,
                        title=kb.title,
                        file_path=kb.file_path,
                        content=kb.content,
                    )
            
            messages.success(request, f'Agent cloned as "{new_name}"!')
            return redirect('agents:agent_detail', pk=new_agent.pk)
    else:
        form = AgentCloneForm(initial={'new_name': f'{original_agent.name} (Copy)'})
    
    context = {
        'form': form,
        'original_agent': original_agent,
    }
    return render(request, 'users/agents/agent_clone.html', context)


@login_required
def agent_toggle_active(request, pk):
    """
    Toggle agent active status.
    """
    agent = get_object_or_404(Agent, pk=pk, user=request.user)
    
    if request.method == 'POST':
        agent.is_active = not agent.is_active
        agent.save()
        
        status = "activated" if agent.is_active else "deactivated"
        messages.success(request, f'Agent "{agent.name}" {status}!')
    
    return redirect('agents:agent_detail', pk=pk)

@login_required
def agent_setup_llm(request, pk):
    """
    Setup LLM integration for an agent.
    """
    from integrations.models import Integration
    
    agent = get_object_or_404(Agent, pk=pk, user=request.user)
    
    # Get existing LLM integrations
    existing_integrations = Integration.objects.filter(
        agent=agent,
        integration_type__in=['openai', 'anthropic']
    )
    
    if request.method == 'POST':
        provider = request.POST.get('provider')  # 'openai' or 'anthropic'
        api_key = request.POST.get('api_key')
        
        if not provider or not api_key:
            messages.error(request, 'Provider and API key are required')
            return redirect('agents:agent_setup_llm', pk=agent.pk)
        
        # Create or update integration
        integration, created = Integration.objects.update_or_create(
            agent=agent,
            integration_type=provider,
            defaults={
                'name': f'{provider.upper()} API',
                'config': {'api_key': api_key},
                'status': Integration.Status.ACTIVE,
                'is_active': True,
            }
        )
        
        action = 'created' if created else 'updated'
        messages.success(request, f'{provider.upper()} integration {action} successfully!')
        return redirect('agents:agent_detail', pk=agent.pk)
    
    context = {
        'agent': agent,
        'existing_integrations': existing_integrations,
    }
    return render(request, 'users/agents/agent_setup_llm.html', context)


@login_required
def agent_delete_integration(request, pk, integration_id):
    """
    Delete an LLM integration for an agent.
    """
    from integrations.models import Integration
    
    agent = get_object_or_404(Agent, pk=pk, user=request.user)
    integration = get_object_or_404(Integration, pk=integration_id, agent=agent)
    
    if request.method == 'POST':
        provider = integration.get_integration_type_display()
        integration.delete()
        messages.success(request, f'{provider} integration deleted!')
    
    return redirect('agents:agent_setup_llm', pk=agent.pk)

class KnowledgeBaseListView(LoginRequiredMixin, ListView):
    """List knowledge bases for an agent."""
    model = KnowledgeBase
    template_name = 'users/agents/knowledge_base_list.html'
    context_object_name = 'knowledge_bases'
    paginate_by = 20
    
    def get_queryset(self):
        agent_id = self.kwargs['agent_id']
        agent = get_object_or_404(Agent, id=agent_id, user=self.request.user)
        return KnowledgeBase.objects.filter(agent=agent)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs['agent_id']
        context['agent'] = get_object_or_404(Agent, id=agent_id, user=self.request.user)
        return context


class KnowledgeBaseCreateView(LoginRequiredMixin, CreateView):
    """Upload and create new knowledge base document."""
    model = KnowledgeBase
    template_name = 'users/agents/knowledge_base_create.html'
    fields = ['title', 'document_type', 'file_path', 'content', 'chunk_size', 'chunk_overlap']
    
    def form_valid(self, form):
        agent_id = self.kwargs['agent_id']
        agent = get_object_or_404(Agent, id=agent_id, user=self.request.user)
        
        form.instance.agent = agent
        form.instance.status = 'pending'
        
        response = super().form_valid(form)
        
        # Trigger async processing
        process_knowledge_base_task.delay(self.object.id)
        
        messages.success(
            self.request,
            f"Knowledge base '{self.object.title}' uploaded. Processing started."
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:knowledge_base_list', kwargs={'agent_id': self.kwargs['agent_id']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs['agent_id']
        context['agent'] = get_object_or_404(Agent, id=agent_id, user=self.request.user)
        return context


class KnowledgeBaseDeleteView(LoginRequiredMixin, DeleteView):
    """Delete knowledge base document."""
    model = KnowledgeBase
    template_name = 'agents/knowledge_base_confirm_delete.html'
    
    def get_queryset(self):
        return KnowledgeBase.objects.filter(agent__user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('agents:knowledge_base_list', kwargs={'agent_id': self.object.agent.id})
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Knowledge base deleted successfully.")
        return super().delete(request, *args, **kwargs)
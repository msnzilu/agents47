"""
Advanced RAG Views - Phase 11
Views for hybrid search configuration and testing
Location: Add to agents/views.py or agents/views/knowledge.py
"""

from django.views.generic import ListView, CreateView, UpdateView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from agents.models import (
    Agent, 
    KnowledgeBase, 
    HybridSearchConfig, 
    QueryExpansion,
    DocumentChunk
)
from agents.services.advanced_rag import HybridSearchService, RetrievalAugmentationService
import json
from django.shortcuts import render
import asyncio


class HybridSearchConfigCreateView(LoginRequiredMixin, CreateView):
    """Create hybrid search configuration for a knowledge base"""
    model = HybridSearchConfig
    template_name = 'agents/hybrid_search_config_form.html'
    fields = [
        'vector_weight', 
        'keyword_weight', 
        'rerank_enabled', 
        'rerank_model',
        'rerank_top_k',
        'es_enabled',
        'es_index_name'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs['kb_id'],
            agent__user=self.request.user
        )
        context['knowledge_base'] = self.knowledge_base
        context['agent'] = self.knowledge_base.agent
        return context
    
    def form_valid(self, form):
        self.knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs['kb_id'],
            agent__user=self.request.user
        )
        
        # Check if config already exists
        if hasattr(self.knowledge_base, 'hybrid_search_config'):
            messages.warning(
                self.request,
                'Hybrid search config already exists. Redirecting to edit.'
            )
            return redirect('agents:hybrid-search-config-update', kb_id=self.knowledge_base.id)
        
        form.instance.knowledge_base = self.knowledge_base
        
        messages.success(
            self.request,
            f'Hybrid search configured for {self.knowledge_base.title}'
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('agents:knowledge-base-detail', kwargs={'pk': self.knowledge_base.id})


class HybridSearchConfigUpdateView(LoginRequiredMixin, UpdateView):
    """Update hybrid search configuration"""
    model = HybridSearchConfig
    template_name = 'agents/hybrid_search_config_form.html'
    fields = [
        'vector_weight', 
        'keyword_weight', 
        'rerank_enabled', 
        'rerank_model',
        'rerank_top_k',
        'es_enabled',
        'es_index_name'
    ]
    
    def get_object(self):
        kb = get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs['kb_id'],
            agent__user=self.request.user
        )
        return get_object_or_404(HybridSearchConfig, knowledge_base=kb)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['knowledge_base'] = self.object.knowledge_base
        context['agent'] = self.object.knowledge_base.agent
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request,
            'Hybrid search configuration updated successfully'
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy(
            'agents:knowledge-base-detail', 
            kwargs={'pk': self.object.knowledge_base.id}
        )


class HybridSearchTestView(LoginRequiredMixin, FormView):
    """Test hybrid search with a query"""
    template_name = 'agents/hybrid_search_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs['kb_id'],
            agent__user=self.request.user
        )
        context['knowledge_base'] = self.knowledge_base
        context['agent'] = self.knowledge_base.agent
        
        # Get config if exists
        try:
            context['config'] = self.knowledge_base.hybrid_search_config
        except HybridSearchConfig.DoesNotExist:
            context['config'] = None
        
        return context
    
    def post(self, request, *args, **kwargs):
        knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs['kb_id'],
            agent__user=request.user
        )
        
        query = request.POST.get('query', '').strip()
        top_k = int(request.POST.get('top_k', 5))
        
        if not query:
            messages.error(request, 'Please enter a search query')
            return redirect('agents:hybrid-search-test', kb_id=knowledge_base.id)
        
        # Perform hybrid search
        try:
            service = HybridSearchService(knowledge_base)
            
            # Run async search
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                service.search(query, top_k=top_k)
            )
            loop.close()
            
            context = self.get_context_data()
            context['query'] = query
            context['results'] = results
            context['result_count'] = len(results)
            
            return self.render_to_response(context)
            
        except Exception as e:
            messages.error(request, f'Search failed: {str(e)}')
            return redirect('agents:hybrid-search-test', kb_id=knowledge_base.id)


class HybridSearchCompareView(LoginRequiredMixin, View):
    """Compare vector-only vs hybrid search results"""
    template_name = 'agents/hybrid_search_compare.html'
    
    def get(self, request, kb_id):
        knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=kb_id,
            agent__user=request.user
        )
        
        context = {
            'knowledge_base': knowledge_base,
            'agent': knowledge_base.agent
        }
        
        return self.render_to_response(context)
    
    def post(self, request, kb_id):
        knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=kb_id,
            agent__user=request.user
        )
        
        query = request.POST.get('query', '').strip()
        top_k = int(request.POST.get('top_k', 5))
        
        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)
        
        try:
            # Get query embedding
            import openai
            from django.conf import settings
            openai.api_key = settings.OPENAI_API_KEY
            
            response = openai.Embedding.create(
                input=query,
                model="text-embedding-ada-002"
            )
            query_embedding = response['data'][0]['embedding']
            
            # Vector-only search
            vector_results = DocumentChunk.similarity_search(
                agent=knowledge_base.agent,
                query_embedding=query_embedding,
                limit=top_k
            )
            
            # Hybrid search (if configured)
            hybrid_results = []
            if hasattr(knowledge_base, 'hybrid_search_config'):
                service = HybridSearchService(knowledge_base)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                hybrid_results = loop.run_until_complete(
                    service.search(query, top_k=top_k)
                )
                loop.close()
            
            return JsonResponse({
                'query': query,
                'vector_results': vector_results,
                'hybrid_results': hybrid_results,
                'vector_count': len(vector_results),
                'hybrid_count': len(hybrid_results)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def render_to_response(self, context):
        from django.shortcuts import render
        return render(self.request, self.template_name, context)


class QueryExpansionListView(LoginRequiredMixin, ListView):
    """View cached query expansions"""
    model = QueryExpansion
    template_name = 'users/agents/advanced_rag/query_expansion_list.html'
    context_object_name = 'query_expansions'
    paginate_by = 20
    
    def get_queryset(self):
        agent_id = self.kwargs.get('agent_id')
        if agent_id:
            agent = get_object_or_404(Agent, pk=agent_id, user=self.request.user)
            return QueryExpansion.objects.filter(agent=agent).order_by('-use_count', '-created_at')
        return QueryExpansion.objects.filter(
            agent__user=self.request.user
        ).order_by('-use_count', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs.get('agent_id')
        if agent_id:
            context['agent'] = get_object_or_404(Agent, pk=agent_id, user=self.request.user)
        return context

class QueryExpansionTestView(LoginRequiredMixin, FormView):
    """Test query expansion with GET form and POST submission"""
    template_name = 'users/agents/advanced_rag/query_expansion_test.html'
    
    def get(self, request, *args, **kwargs):
        """Display the test form"""
        return render(request, self.template_name)
    
    def post(self, request, *args, **kwargs):
        """Process query expansion"""
        query = request.POST.get('query', '').strip()
        
        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)
        
        try:
            import openai
            from django.conf import settings
            
            openai.api_key = settings.OPENAI_API_KEY
            
            # Generate expansions
            prompt = f"""Generate 3-5 alternative phrasings or synonymous queries for:
"{query}"

Return only the queries, one per line, without numbers or bullets."""
            
            response = openai.ChatCompletion.create(
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
            
            # Return HTML response instead of JSON for better UX
            context = {
                'original_query': query,
                'expanded_queries': expansions,
                'count': len(expansions)
            }
            return render(request, self.template_name, context)
            
        except Exception as e:
            context = {
                'error': str(e),
                'original_query': query
            }
            return render(request, self.template_name, context)

# class QueryExpansionTestView(LoginRequiredMixin, View):
#     """Test query expansion"""

#     def get(self, request, *args, **kwargs):
#         """Display the test form"""
#         return render(request, self.template_name)
    
#     def post(self, request):
#         query = request.POST.get('query', '').strip()
        
#         if not query:
#             return JsonResponse({'error': 'Query is required'}, status=400)
        
#         try:
#             import openai
#             from django.conf import settings
#             openai.api_key = settings.OPENAI_API_KEY
            
#             # Generate expansions
#             prompt = f"""Generate 3-5 alternative phrasings or synonymous queries for:
# "{query}"

# Return only the queries, one per line, without numbers or bullets."""
            
#             response = openai.ChatCompletion.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "You are a query expansion assistant."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 temperature=0.7,
#                 max_tokens=200
#             )
            
#             expansions = [
#                 line.strip() 
#                 for line in response.choices[0].message.content.split('\n')
#                 if line.strip()
#             ]
            
#             return JsonResponse({
#                 'original_query': query,
#                 'expanded_queries': expansions,
#                 'count': len(expansions)
#             })
            
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)


class KnowledgeBaseSearchAPIView(LoginRequiredMixin, View):
    """API endpoint for searching knowledge base with hybrid search"""
    
    def post(self, request, kb_id):
        knowledge_base = get_object_or_404(
            KnowledgeBase,
            pk=kb_id,
            agent__user=request.user
        )
        
        try:
            data = json.loads(request.body)
            query = data.get('query', '').strip()
            top_k = data.get('top_k', 5)
            use_hybrid = data.get('use_hybrid', True)
            
            if not query:
                return JsonResponse({'error': 'Query is required'}, status=400)
            
            # Use hybrid search if available and requested
            if use_hybrid and hasattr(knowledge_base, 'hybrid_search_config'):
                service = HybridSearchService(knowledge_base)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(
                    service.search(query, top_k=top_k)
                )
                loop.close()
                search_type = 'hybrid'
            else:
                # Fall back to vector-only search
                import openai
                from django.conf import settings
                openai.api_key = settings.OPENAI_API_KEY
                
                response = openai.Embedding.create(
                    input=query,
                    model="text-embedding-ada-002"
                )
                query_embedding = response['data'][0]['embedding']
                
                results = DocumentChunk.similarity_search(
                    agent=knowledge_base.agent,
                    query_embedding=query_embedding,
                    limit=top_k
                )
                search_type = 'vector'
            
            return JsonResponse({
                'success': True,
                'query': query,
                'search_type': search_type,
                'results': results,
                'count': len(results)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class RAGTestView(LoginRequiredMixin, FormView):
    """Test complete RAG pipeline with agent"""
    template_name = 'agents/rag_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs['agent_id']
        context['agent'] = get_object_or_404(Agent, pk=agent_id, user=self.request.user)
        context['knowledge_bases'] = context['agent'].knowledge_bases.filter(
            is_active=True,
            status='completed'
        )
        return context
    
    def post(self, request, *args, **kwargs):
        agent = get_object_or_404(Agent, pk=self.kwargs['agent_id'], user=request.user)
        
        query = request.POST.get('query', '').strip()
        top_k = int(request.POST.get('top_k', 3))
        
        if not query:
            messages.error(request, 'Please enter a query')
            return redirect('agents:rag-test', agent_id=agent.id)
        
        try:
            # Use RAG service
            rag_service = RetrievalAugmentationService(agent)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            augmented_prompt, sources = loop.run_until_complete(
                rag_service.retrieve_and_augment(query, top_k=top_k)
            )
            loop.close()
            
            context = self.get_context_data()
            context['query'] = query
            context['augmented_prompt'] = augmented_prompt
            context['sources'] = sources
            context['source_count'] = len(sources)
            
            # Optionally: Execute with agent and get response
            # This requires your agent execution code
            
            return self.render_to_response(context)
            
        except Exception as e:
            messages.error(request, f'RAG test failed: {str(e)}')
            return redirect('agents:rag-test', agent_id=agent.id)
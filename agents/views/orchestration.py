"""
Multi-Agent Orchestration Views - Phase 11
Location: agents/views/orchestration.py
"""

from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, 
    DetailView, FormView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from agents.models import (
    Agent,
    AgentOrchestration,
    OrchestrationParticipant,
    OrchestrationExecution,
    AgentCommunication
)
from ..services.orchestration import OrchestrationService
import json
from datetime import datetime
from django.db.models import Sum, Count, Q


class OrchestrationListView(LoginRequiredMixin, ListView):
    """List all orchestrations for the user"""
    model = AgentOrchestration
    template_name = 'users/agents/orchestration/orchestration_list.html'
    context_object_name = 'orchestrations'
    paginate_by = 20
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(
            user=self.request.user
        ).prefetch_related('participant_agents').select_related('orchestrator_agent')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate statistics from the full queryset (not paginated)
        orchestrations = self.get_queryset()
        
        # Get aggregated stats using Django's aggregate functions
        stats = orchestrations.aggregate(
            active_count=Count('id', filter=Q(is_active=True)),
            total_executions=Sum('total_executions'),
            successful_executions=Sum('successful_executions')
        )
        
        # Ensure we have default values for the template
        context['stats'] = {
            'active_count': stats.get('active_count') or 0,
            'total_executions': stats.get('total_executions') or 0,
            'successful_executions': stats.get('successful_executions') or 0,
        }
        
        return context

# class OrchestrationListView(LoginRequiredMixin, ListView):
#     """List all orchestrations for the user"""
#     model = AgentOrchestration
#     template_name = 'users/agents/orchestration/orchestration_list.html'
#     context_object_name = 'orchestrations'
#     paginate_by = 20
    
#     def get_queryset(self):
#         return AgentOrchestration.objects.filter(
#             user=self.request.user
#         ).prefetch_related('participant_agents').select_related('orchestrator_agent')


class OrchestrationCreateView(LoginRequiredMixin, CreateView):
    """Create new orchestration"""
    model = AgentOrchestration
    template_name = 'users/agents/orchestration/orchestration_form.html'
    fields = ['name', 'orchestrator_agent', 'strategy', 'workflow_config']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter orchestrator agents to only user's agents
        form.fields['orchestrator_agent'].queryset = Agent.objects.filter(
            user=self.request.user,
            is_active=True
        )
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_agents'] = Agent.objects.filter(
            user=self.request.user,
            is_active=True
        )
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Set default workflow config if empty
        if not form.instance.workflow_config:
            form.instance.workflow_config = {
                'steps': [],
                'synthesis_strategy': 'summarize',
                'max_parallel_agents': 3
            }
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            f'Orchestration "{self.object.name}" created successfully. Add participant agents next.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:orchestration-detail', kwargs={'pk': self.object.pk})


class OrchestrationDetailView(LoginRequiredMixin, DetailView):
    """View orchestration details"""
    model = AgentOrchestration
    template_name = 'agents/orchestration/orchestration_detail.html'
    context_object_name = 'orchestration'
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get participants
        context['participants'] = OrchestrationParticipant.objects.filter(
            orchestration=self.object
        ).select_related('agent').order_by('execution_order')
        
        # Get recent executions
        context['recent_executions'] = self.object.executions.all()[:10]
        
        # Calculate success rate
        if self.object.total_executions > 0:
            context['success_rate'] = (
                self.object.successful_executions / self.object.total_executions * 100
            )
        else:
            context['success_rate'] = 0
        
        # Get available agents for adding participants
        context['available_agents'] = Agent.objects.filter(
            user=self.request.user,
            is_active=True
        ).exclude(
            id__in=context['participants'].values_list('agent_id', flat=True)
        ).exclude(
            id=self.object.orchestrator_agent_id
        )
        
        # Validate workflow
        errors = self.object.validate_workflow()
        context['workflow_errors'] = errors
        
        return context


class OrchestrationUpdateView(LoginRequiredMixin, UpdateView):
    """Update orchestration configuration"""
    model = AgentOrchestration
    template_name = 'users/agents/orchestration/orchestration_form.html'
    fields = ['name', 'orchestrator_agent', 'strategy', 'workflow_config', 'is_active']
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(user=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['orchestrator_agent'].queryset = Agent.objects.filter(
            user=self.request.user,
            is_active=True
        )
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Orchestration updated successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('agents:orchestration-detail', kwargs={'pk': self.object.pk})


class OrchestrationDeleteView(LoginRequiredMixin, DeleteView):
    """Delete orchestration"""
    model = AgentOrchestration
    template_name = 'agents/orchestration/orchestration_confirm_delete.html'
    success_url = reverse_lazy('agents:orchestration-list')
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Orchestration deleted successfully')
        return super().delete(request, *args, **kwargs)


class OrchestrationParticipantAddView(LoginRequiredMixin, View):
    """Add participant agent to orchestration"""
    
    def post(self, request, orchestration_id):
        orchestration = get_object_or_404(
            AgentOrchestration,
            pk=orchestration_id,
            user=request.user
        )
        
        agent_id = request.POST.get('agent_id')
        role = request.POST.get('role', 'participant')
        execution_order = request.POST.get('execution_order', 0)
        is_optional = request.POST.get('is_optional') == 'on'
        
        agent = get_object_or_404(Agent, pk=agent_id, user=request.user)
        
        # Check if already a participant
        if OrchestrationParticipant.objects.filter(
            orchestration=orchestration,
            agent=agent
        ).exists():
            messages.warning(request, f'{agent.name} is already a participant')
            return redirect('agents:orchestration-detail', pk=orchestration.id)
        
        # Create participant
        OrchestrationParticipant.objects.create(
            orchestration=orchestration,
            agent=agent,
            role=role,
            execution_order=execution_order,
            is_optional=is_optional
        )
        
        messages.success(request, f'{agent.name} added as participant')
        return redirect('agents:orchestration-detail', pk=orchestration.id)


class OrchestrationParticipantRemoveView(LoginRequiredMixin, View):
    """Remove participant agent from orchestration"""
    
    def post(self, request, orchestration_id, participant_id):
        orchestration = get_object_or_404(
            AgentOrchestration,
            pk=orchestration_id,
            user=request.user
        )
        
        participant = get_object_or_404(
            OrchestrationParticipant,
            pk=participant_id,
            orchestration=orchestration
        )
        
        agent_name = participant.agent.name
        participant.delete()
        
        messages.success(request, f'{agent_name} removed from orchestration')
        return redirect('agents:orchestration-detail', pk=orchestration.id)


class OrchestrationExecuteView(LoginRequiredMixin, View):
    """Execute orchestration workflow"""
    
    def post(self, request, orchestration_id):
        orchestration = get_object_or_404(
            AgentOrchestration,
            pk=orchestration_id,
            user=request.user,
            is_active=True
        )
        
        user_query = request.POST.get('query', '').strip()
        
        if not user_query:
            return JsonResponse({'error': 'Query is required'}, status=400)
        
        # Check if orchestration has participants
        if not orchestration.participant_agents.exists():
            return JsonResponse({
                'error': 'Orchestration has no participant agents'
            }, status=400)
        
        # Validate workflow
        errors = orchestration.validate_workflow()
        if errors:
            return JsonResponse({
                'error': 'Invalid workflow configuration',
                'details': errors
            }, status=400)
        
        try:
            # Create execution record
            execution = OrchestrationExecution.objects.create(
                orchestration=orchestration,
                user_query=user_query,
                status='pending'
            )
            
            # Trigger async execution
            from agents.tasks import execute_orchestration_task
            execute_orchestration_task.delay(execution.id)
            
            return JsonResponse({
                'success': True,
                'execution_id': execution.id,
                'message': 'Orchestration execution started'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)


class OrchestrationExecutionDetailView(LoginRequiredMixin, DetailView):
    """View orchestration execution details"""
    model = OrchestrationExecution
    template_name = 'agents/orchestration/execution_detail.html'
    context_object_name = 'execution'
    
    def get_queryset(self):
        return OrchestrationExecution.objects.filter(
            orchestration__user=self.request.user
        ).select_related('orchestration')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get agent communications
        context['communications'] = AgentCommunication.objects.filter(
            execution=self.object
        ).select_related('from_agent', 'to_agent').order_by('timestamp')
        
        # Calculate execution time
        if self.object.started_at and self.object.completed_at:
            context['execution_time'] = (
                self.object.completed_at - self.object.started_at
            ).total_seconds()
        
        return context


class OrchestrationExecutionListView(LoginRequiredMixin, ListView):
    """List orchestration executions"""
    model = OrchestrationExecution
    template_name = 'users/agents/orchestration/execution_list.html'
    context_object_name = 'executions'
    paginate_by = 20
    
    def get_queryset(self):
        orchestration_id = self.kwargs.get('orchestration_id')
        
        if orchestration_id:
            orchestration = get_object_or_404(
                AgentOrchestration,
                pk=orchestration_id,
                user=self.request.user
            )
            return orchestration.executions.all()
        
        return OrchestrationExecution.objects.filter(
            orchestration__user=self.request.user
        ).select_related('orchestration')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        orchestration_id = self.kwargs.get('orchestration_id')
        if orchestration_id:
            context['orchestration'] = get_object_or_404(
                AgentOrchestration,
                pk=orchestration_id,
                user=self.request.user
            )
        
        return context


class OrchestrationTestView(LoginRequiredMixin, FormView):
    """Test orchestration with sample query"""
    template_name = 'agents/orchestration/orchestration_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        orchestration_id = self.kwargs['orchestration_id']
        context['orchestration'] = get_object_or_404(
            AgentOrchestration,
            pk=orchestration_id,
            user=self.request.user
        )
        
        context['participants'] = OrchestrationParticipant.objects.filter(
            orchestration=context['orchestration']
        ).select_related('agent')
        
        return context
    
    def post(self, request, *args, **kwargs):
        orchestration = get_object_or_404(
            AgentOrchestration,
            pk=self.kwargs['orchestration_id'],
            user=request.user
        )
        
        query = request.POST.get('query', '').strip()
        
        if not query:
            messages.error(request, 'Please enter a test query')
            return redirect('agents:orchestration-test', orchestration_id=orchestration.id)
        
        try:
            # Execute orchestration synchronously for testing
            service = OrchestrationService(orchestration)
            result = service.execute_sync(query)
            
            context = self.get_context_data()
            context['test_query'] = query
            context['test_result'] = result
            
            return self.render_to_response(context)
            
        except Exception as e:
            messages.error(request, f'Test execution failed: {str(e)}')
            return redirect('agents:orchestration-test', orchestration_id=orchestration.id)


class OrchestrationMetricsView(LoginRequiredMixin, DetailView):
    """View orchestration metrics and analytics"""
    model = AgentOrchestration
    template_name = 'agents/orchestration/orchestration_metrics.html'
    context_object_name = 'orchestration'
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all executions
        executions = self.object.executions.all()
        
        # Calculate metrics
        total = executions.count()
        successful = executions.filter(status='completed').count()
        failed = executions.filter(status='failed').count()
        
        context['total_executions'] = total
        context['successful_executions'] = successful
        context['failed_executions'] = failed
        context['success_rate'] = (successful / total * 100) if total > 0 else 0
        
        # Average execution time
        completed = executions.filter(
            status='completed',
            execution_time_ms__isnull=False
        )
        
        if completed.exists():
            from django.db.models import Avg
            avg_time = completed.aggregate(Avg('execution_time_ms'))['execution_time_ms__avg']
            context['avg_execution_time'] = avg_time
        else:
            context['avg_execution_time'] = 0
        
        # Recent executions for chart
        recent = executions.order_by('-created_at')[:30]
        context['recent_executions_chart'] = list(recent.values(
            'created_at', 'status', 'execution_time_ms'
        ))
        
        # Agent participation stats
        from django.db.models import Count
        agent_stats = AgentCommunication.objects.filter(
            execution__orchestration=self.object
        ).values('from_agent__name').annotate(
            message_count=Count('id')
        ).order_by('-message_count')
        
        context['agent_stats'] = agent_stats
        
        return context


class OrchestrationCloneView(LoginRequiredMixin, View):
    """Clone an orchestration"""
    
    def post(self, request, orchestration_id):
        original = get_object_or_404(
            AgentOrchestration,
            pk=orchestration_id,
            user=request.user
        )
        
        # Create clone
        clone = AgentOrchestration.objects.create(
            name=f"{original.name} (Copy)",
            user=request.user,
            orchestrator_agent=original.orchestrator_agent,
            strategy=original.strategy,
            workflow_config=original.workflow_config.copy(),
            is_active=False  # Clones start inactive
        )
        
        # Clone participants
        for participant in original.orchestrationparticipant_set.all():
            OrchestrationParticipant.objects.create(
                orchestration=clone,
                agent=participant.agent,
                role=participant.role,
                execution_order=participant.execution_order,
                is_optional=participant.is_optional
            )
        
        messages.success(
            request,
            f'Orchestration cloned as "{clone.name}". Review and activate when ready.'
        )
        
        return redirect('agents:orchestration-detail', pk=clone.id)


class OrchestrationWorkflowBuilderView(LoginRequiredMixin, DetailView):
    """Visual workflow builder for orchestration"""
    model = AgentOrchestration
    template_name = 'agents/orchestration/workflow_builder.html'
    context_object_name = 'orchestration'
    
    def get_queryset(self):
        return AgentOrchestration.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get participants
        context['participants'] = OrchestrationParticipant.objects.filter(
            orchestration=self.object
        ).select_related('agent')
        
        # Get workflow config for visualization
        context['workflow_json'] = json.dumps(self.object.workflow_config, indent=2)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Save workflow configuration from builder"""
        self.object = self.get_object()
        
        try:
            workflow_config = json.loads(request.POST.get('workflow_config', '{}'))
            
            # Validate workflow
            self.object.workflow_config = workflow_config
            errors = self.object.validate_workflow()
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            
            self.object.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Workflow saved successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'errors': ['Invalid JSON format']
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'errors': [str(e)]
            }, status=500)
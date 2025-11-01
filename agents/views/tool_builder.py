"""
Custom Tool Builder Views - Phase 11
Location: agents/views/custom_tools.py
"""

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from agents.models import CustomTool, ToolParameter, ToolExecution
import json
import time
from django.db import models


class CustomToolListView(LoginRequiredMixin, ListView):
    """List all custom tools"""
    model = CustomTool
    template_name = 'users/agents/tools_builder/list.html'
    context_object_name = 'tools'
    paginate_by = 20
    
    def get_queryset(self):
        return CustomTool.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Stats
        tools = self.get_queryset()
        context['total_tools'] = tools.count()
        context['total_executions'] = tools.aggregate(
            total=models.Sum('execution_count')
        )['total'] or 0
        context['success_rate'] = self._calculate_success_rate(tools)
        
        return context
    
    def _calculate_success_rate(self, tools):
        total_exec = sum(t.execution_count for t in tools)
        total_success = sum(t.success_count for t in tools)
        if total_exec == 0:
            return 0
        return round((total_success / total_exec) * 100, 1)


class CustomToolBuilderView(LoginRequiredMixin, TemplateView):
    """Visual no-code tool builder interface"""
    template_name = 'users/agents/tools_builder/builder.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # If editing existing tool
        tool_id = self.kwargs.get('pk')
        if tool_id:
            tool = get_object_or_404(CustomTool, pk=tool_id, user=self.request.user)
            context['tool'] = tool
            context['mode'] = 'edit'
        else:
            context['mode'] = 'create'
        
        return context


class CustomToolDetailView(LoginRequiredMixin, DetailView):
    """View custom tool details and executions"""
    model = CustomTool
    template_name = 'agents/custom_tools/detail.html'
    context_object_name = 'tool'
    
    def get_queryset(self):
        return CustomTool.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recent executions
        context['recent_executions'] = self.object.executions.all()[:20]
        
        # Success rate
        if self.object.execution_count > 0:
            context['success_rate'] = round(
                (self.object.success_count / self.object.execution_count) * 100, 
                1
            )
        else:
            context['success_rate'] = 0
        
        # Average execution time
        recent_execs = self.object.executions.all()[:100]
        if recent_execs:
            avg_time = sum(e.execution_time_ms for e in recent_execs) / len(recent_execs)
            context['avg_execution_time'] = round(avg_time, 0)
        else:
            context['avg_execution_time'] = 0
        
        return context


class CustomToolCreateAPIView(LoginRequiredMixin, View):
    """API endpoint to create custom tool"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Create tool
            tool = CustomTool.objects.create(
                user=request.user,
                name=data.get('name'),
                description=data.get('description'),
                icon=data.get('icon', '🔧'),
                category=data.get('category', ''),
                tool_type='api',
                endpoint_url=data.get('endpoint_url'),
                http_method=data.get('http_method', 'GET'),
                auth_type=data.get('auth_type', 'none'),
                auth_config=data.get('auth_config', {}),
                headers=data.get('headers', {}),
                parameters=data.get('parameters', []),
                request_body_template=data.get('request_body_template', ''),
                tags=data.get('tags', [])
            )
            
            return JsonResponse({
                'success': True,
                'tool_id': tool.id,
                'message': 'Tool created successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CustomToolUpdateAPIView(LoginRequiredMixin, View):
    """API endpoint to update custom tool"""
    
    def post(self, request, pk):
        try:
            tool = get_object_or_404(CustomTool, pk=pk, user=request.user)
            data = json.loads(request.body)
            
            # Update fields
            tool.name = data.get('name', tool.name)
            tool.description = data.get('description', tool.description)
            tool.icon = data.get('icon', tool.icon)
            tool.category = data.get('category', tool.category)
            tool.endpoint_url = data.get('endpoint_url', tool.endpoint_url)
            tool.http_method = data.get('http_method', tool.http_method)
            tool.auth_type = data.get('auth_type', tool.auth_type)
            tool.auth_config = data.get('auth_config', tool.auth_config)
            tool.headers = data.get('headers', tool.headers)
            tool.parameters = data.get('parameters', tool.parameters)
            tool.request_body_template = data.get('request_body_template', tool.request_body_template)
            tool.tags = data.get('tags', tool.tags)
            
            tool.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Tool updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CustomToolTestAPIView(LoginRequiredMixin, View):
    """API endpoint to test tool execution"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            tool_config = data.get('tool')
            parameters = data.get('parameters', {})
            
            # Create temporary tool instance for testing
            temp_tool = CustomTool(
                user=request.user,
                endpoint_url=tool_config.get('endpoint_url'),
                http_method=tool_config.get('http_method', 'GET'),
                auth_type=tool_config.get('auth_type', 'none'),
                auth_config=tool_config.get('auth_config', {}),
                headers=tool_config.get('headers', {}),
                request_body_template=tool_config.get('request_body_template', '')
            )
            
            # Execute
            start_time = time.time()
            result = temp_tool.execute(parameters)
            execution_time = int((time.time() - start_time) * 1000)
            
            result['execution_time_ms'] = execution_time
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CustomToolExecuteView(LoginRequiredMixin, View):
    """Execute a custom tool"""
    
    def post(self, request, pk):
        try:
            tool = get_object_or_404(CustomTool, pk=pk, user=request.user)
            data = json.loads(request.body)
            parameters = data.get('parameters', {})
            
            # Execute tool
            start_time = time.time()
            result = tool.execute(parameters)
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log execution
            ToolExecution.objects.create(
                custom_tool=tool,
                input_parameters=parameters,
                output_data=result.get('data', {}),
                status_code=result.get('status_code'),
                execution_time_ms=execution_time,
                success=result.get('success', False),
                error_message=result.get('error', '')
            )
            
            result['execution_time_ms'] = execution_time
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CustomToolDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a custom tool"""
    model = CustomTool
    success_url = reverse_lazy('agents:custom-tools-list')
    
    def get_queryset(self):
        return CustomTool.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Tool deleted successfully')
        return super().delete(request, *args, **kwargs)


class CustomToolToggleView(LoginRequiredMixin, View):
    """Toggle tool active status"""
    
    def post(self, request, pk):
        tool = get_object_or_404(CustomTool, pk=pk, user=request.user)
        tool.is_active = not tool.is_active
        tool.save()
        
        return JsonResponse({
            'success': True,
            'is_active': tool.is_active
        })


class CustomToolCloneView(LoginRequiredMixin, View):
    """Clone a custom tool"""
    
    def post(self, request, pk):
        original = get_object_or_404(CustomTool, pk=pk)
        
        # Check if public or owned by user
        if not original.is_public and original.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Tool is not public'
            }, status=403)
        
        # Clone tool
        cloned = CustomTool.objects.create(
            user=request.user,
            name=f"{original.name} (Copy)",
            description=original.description,
            icon=original.icon,
            category=original.category,
            tool_type=original.tool_type,
            endpoint_url=original.endpoint_url,
            http_method=original.http_method,
            auth_type='none',  # Don't copy auth credentials
            auth_config={},
            headers=original.headers.copy(),
            parameters=original.parameters.copy(),
            request_body_template=original.request_body_template,
            response_mapping=original.response_mapping.copy(),
            tags=original.tags.copy()
        )
        
        messages.success(request, f'Tool "{original.name}" cloned successfully')
        
        return JsonResponse({
            'success': True,
            'tool_id': cloned.id
        })


# View 1: Template Gallery (shows the templates)
class CustomToolTemplatesView(LoginRequiredMixin, TemplateView):
    """Pre-built tool templates"""
    template_name = 'users/agents/tools_builder/templates.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pre-built templates
        context['templates'] = [
            {
                'name': 'Weather API',
                'icon': '🌤️',
                'description': 'Get current weather data',
                'category': 'data',
                'config': {
                    'endpoint_url': 'https://api.openweathermap.org/data/2.5/weather',
                    'http_method': 'GET',
                    'parameters': [
                        {'name': 'city', 'type': 'string', 'required': True},
                        {'name': 'units', 'type': 'string', 'required': False}
                    ]
                }
            },
            {
                'name': 'Send Email',
                'icon': '📧',
                'description': 'Send emails via API',
                'category': 'communication',
                'config': {
                    'endpoint_url': 'https://api.sendgrid.com/v3/mail/send',
                    'http_method': 'POST',
                    'auth_type': 'bearer',
                    'parameters': [
                        {'name': 'to', 'type': 'string', 'required': True},
                        {'name': 'subject', 'type': 'string', 'required': True},
                        {'name': 'body', 'type': 'string', 'required': True}
                    ]
                }
            },
            {
                'name': 'Database Query',
                'icon': '🗄️',
                'description': 'Query your database',
                'category': 'data',
                'config': {
                    'endpoint_url': 'https://your-api.com/query',
                    'http_method': 'POST'
                }
            },
            {
                'name': 'Slack Notification',
                'icon': '💬',
                'description': 'Send messages to Slack',
                'category': 'communication',
                'config': {
                    'endpoint_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
                    'http_method': 'POST',
                    'parameters': [
                        {'name': 'message', 'type': 'string', 'required': True}
                    ]
                }
            }
        ]
        
        return context


# View 2: Tool Builder (creates the tool)
class CustomToolBuilderView(LoginRequiredMixin, CreateView):
    """Create custom tool - with optional template pre-fill"""
    model = CustomTool
    template_name = 'users/agents/tools_builder/builder.html'
    fields = ['name', 'description', 'icon', 'category', 'endpoint_url', 
              'http_method', 'auth_type', 'headers', 'request_body_template']
    
    def get_initial(self):
        """Pre-fill form with template data if template parameter exists"""
        initial = super().get_initial()
        
        template_name = self.request.GET.get('template')
        if template_name:
            template_data = self.get_template_data(template_name)
            if template_data:
                initial.update({
                    'name': template_data['name'],
                    'description': template_data['description'],
                    'icon': template_data['icon'],
                    'category': template_data.get('category', ''),
                    'endpoint_url': template_data['config'].get('endpoint_url', ''),
                    'http_method': template_data['config'].get('http_method', 'GET'),
                    'auth_type': template_data['config'].get('auth_type', 'none'),
                })
        
        return initial
    
    def get_template_data(self, template_name):
        """Get template configuration by name"""
        templates = {
            'weather-api': {
                'name': 'Weather API',
                'icon': '🌤️',
                'description': 'Get current weather data',
                'category': 'data',
                'config': {
                    'endpoint_url': 'https://api.openweathermap.org/data/2.5/weather',
                    'http_method': 'GET',
                }
            },
            'send-email': {
                'name': 'Send Email',
                'icon': '📧',
                'description': 'Send emails via API',
                'category': 'communication',
                'config': {
                    'endpoint_url': 'https://api.sendgrid.com/v3/mail/send',
                    'http_method': 'POST',
                    'auth_type': 'bearer',
                }
            },
            'database-query': {
                'name': 'Database Query',
                'icon': '🗄️',
                'description': 'Query your database',
                'category': 'data',
                'config': {
                    'endpoint_url': 'https://your-api.com/query',
                    'http_method': 'POST'
                }
            },
            'slack-notification': {
                'name': 'Slack Notification',
                'icon': '💬',
                'description': 'Send messages to Slack',
                'category': 'communication',
                'config': {
                    'endpoint_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
                    'http_method': 'POST',
                }
            }
        }
        
        return templates.get(template_name)
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


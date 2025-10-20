"""
Custom Admin Views for User and Agent Management.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView, DeleteView, DetailView
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta

from agents.models import Agent
from chat.models import Conversation, Message
# from analytics.models import UsageLog

User = get_user_model()


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff access."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, 'You need staff permissions to access this page.')
        return redirect('home')


@staff_member_required
def admin_dashboard(request):
    """
    Main admin dashboard with statistics and overview.
    """
    # Time ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=week_ago).count()
    new_users_this_month = User.objects.filter(created_at__gte=month_ago).count()
    
    # Agent statistics
    total_agents = Agent.objects.count()
    active_agents = Agent.objects.filter(is_active=True).count()
    agents_by_use_case = Agent.objects.values('use_case').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Conversation statistics
    total_conversations = Conversation.objects.count()
    conversations_this_week = Conversation.objects.filter(
        created_at__gte=week_ago
    ).count()
    total_messages = Message.objects.count()
    
    # Recent users
    recent_users = User.objects.order_by('-created_at')[:10]
    
    # Recent agents
    recent_agents = Agent.objects.select_related('user').order_by('-created_at')[:10]
    
    # Top users by agent count
    top_users = User.objects.annotate(
        agent_count=Count('agents')
    ).filter(agent_count__gt=0).order_by('-agent_count')[:5]
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'new_users_this_month': new_users_this_month,
        'total_agents': total_agents,
        'active_agents': active_agents,
        'agents_by_use_case': agents_by_use_case,
        'total_conversations': total_conversations,
        'conversations_this_week': conversations_this_week,
        'total_messages': total_messages,
        'recent_users': recent_users,
        'recent_agents': recent_agents,
        'top_users': top_users,
    }
    
    return render(request, 'admin/dashboard.html', context)


class AdminUserListView(StaffRequiredMixin, ListView):
    """List all users with filtering and search."""
    model = User
    template_name = 'admin/users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.annotate(
            agent_count_annotated=Count('agents'),
            conversation_count_annotated=Count('agents__conversations')
        ).order_by('-created_at')


        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(company__icontains=search)
            )
        
        # Filter by active status
        is_active = self.request.GET.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        # Filter by staff status
        is_staff = self.request.GET.get('is_staff')
        if is_staff == 'true':
            queryset = queryset.filter(is_staff=True)
        elif is_staff == 'false':
            queryset = queryset.filter(is_staff=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['is_active'] = self.request.GET.get('is_active', '')
        context['is_staff'] = self.request.GET.get('is_staff', '')
        return context


class AdminUserDetailView(StaffRequiredMixin, DetailView):
    """Detailed view of a single user."""
    model = User
    template_name = 'myadmin/user_detail.html'
    context_object_name = 'user_obj'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()
        
        # User's agents
        context['agents'] = Agent.objects.filter(user=user_obj).annotate(
            conversation_count=Count('conversations')
        ).order_by('-created_at')
        
        # Recent conversations
        context['recent_conversations'] = Conversation.objects.filter(
            agent__user=user_obj
        ).select_related('agent').order_by('-updated_at')[:10]
        
        return context


@staff_member_required
def admin_user_toggle_active(request, pk):
    """Toggle user active status."""
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        
        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f'User {user.email} has been {status}.')
    
    return redirect('myadmin:user_detail', pk=pk)


@staff_member_required
def admin_user_toggle_staff(request, pk):
    """Toggle user staff status."""
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        # Prevent removing your own staff status
        if user == request.user:
            messages.error(request, 'You cannot remove your own staff status.')
        else:
            user.is_staff = not user.is_staff
            user.save()
            
            status = "granted" if user.is_staff else "revoked"
            messages.success(request, f'Staff access {status} for {user.email}.')
    
    return redirect('myadmin:user_detail', pk=pk)

@staff_member_required
def admin_user_delete(request, pk):
    """Delete a user (admin only)."""
    user = get_object_or_404(User, pk=pk)
    
    # Prevent deleting superusers
    if user.is_superuser:
        messages.error(request, 'Cannot delete superuser accounts.')
        return redirect('myadmin:user_detail', pk=pk)
    
    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('myadmin:user_detail', pk=pk)
    
    if request.method == 'POST':
        user_email = user.email
        agent_count = user.agents.count()
        user.delete()
        messages.success(
            request, 
            f'User "{user_email}" and {agent_count} associated agent(s) have been deleted.'
        )
        return redirect('myadmin:user_list')
    
    # GET request - show confirmation page
    context = {
        'user_obj': user,
        'agent_count': user.agents.count(),
    }
    return render(request, 'admin/users/user_confirm_delete.html', context)

class AdminAgentListView(StaffRequiredMixin, ListView):
    """List all agents with filtering and search."""
    model = Agent
    template_name = 'admin/agents/agent_list.html'
    context_object_name = 'agents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Agent.objects.select_related('user').order_by('-created_at')

        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(user__email__icontains=search)
            )
        
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
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['use_case'] = self.request.GET.get('use_case', '')
        context['is_active'] = self.request.GET.get('is_active', '')
        context['use_cases'] = Agent.UseCase.choices
        return context


class AdminAgentDetailView(StaffRequiredMixin, DetailView):
    """Detailed view of a single agent."""
    model = Agent
    template_name = 'admin/agents/agent_detail.html'
    context_object_name = 'agent'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        
        # Agent's conversations
        context['conversations'] = Conversation.objects.filter(
            agent=agent
        ).annotate(
            message_count=Count('messages')
        ).order_by('-updated_at')[:20]
        
        # Total messages
        context['total_messages'] = Message.objects.filter(
            conversation__agent=agent
        ).count()
        
        return context


@staff_member_required
def admin_agent_toggle_active(request, pk):
    """Toggle agent active status."""
    agent = get_object_or_404(Agent, pk=pk)
    
    if request.method == 'POST':
        agent.is_active = not agent.is_active
        agent.save()
        
        status = "activated" if agent.is_active else "deactivated"
        messages.success(request, f'Agent "{agent.name}" has been {status}.')
    
    return redirect('myadmin:agent_detail', pk=pk)


@staff_member_required
def admin_agent_delete(request, pk):
    """Delete an agent (admin only)."""
    agent = get_object_or_404(Agent, pk=pk)
    
    if request.method == 'POST':
        agent_name = agent.name
        agent.delete()
        messages.success(request, f'Agent "{agent_name}" has been deleted.')
        return redirect('myadmin:agent_list')
    
    return render(request, 'myadmin/agent_confirm_delete.html', {'agent': agent})
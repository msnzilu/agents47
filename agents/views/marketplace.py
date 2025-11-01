"""
Agent Marketplace Views - Phase 11
Location: agents/views/marketplace.py
"""

from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from django.db.models import Q, Avg, Count
from django.db import models
from agents.models import (
    Agent,
    MarketplaceAgent,
    AgentInstallation,
    AgentReview,
    ReviewHelpfulness
)
from datetime import datetime

"""
Marketplace Dashboard View
Add this to agents/views/marketplace.py
"""

class MarketplaceDashboardView(LoginRequiredMixin, ListView):
    """Seller dashboard showing listings and stats"""
    model = MarketplaceAgent
    template_name = 'users/agents/marketplace/dashboard.html'
    context_object_name = 'listings'
    paginate_by = 10
    
    def get_queryset(self):
        return MarketplaceAgent.objects.filter(
            publisher=self.request.user
        ).select_related('agent').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's marketplace listings
        user_listings = MarketplaceAgent.objects.filter(publisher=self.request.user)
        
        # Calculate stats
        context['total_listings'] = user_listings.count()
        context['total_sales'] = user_listings.aggregate(
            total=models.Sum('install_count')
        )['total'] or 0
        
        # Calculate revenue
        total_revenue = 0
        for listing in user_listings:
            if not listing.is_free:
                total_revenue += (listing.price * listing.install_count)
        context['total_revenue'] = total_revenue
        
        # This month sales (last 30 days)
        from django.utils import timezone
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        recent_installations = AgentInstallation.objects.filter(
            marketplace_agent__publisher=self.request.user,
            installed_at__gte=thirty_days_ago
        )
        context['sales_this_month'] = recent_installations.count()
        
        # Revenue this month
        revenue_this_month = 0
        for installation in recent_installations:
            if not installation.marketplace_agent.is_free:
                revenue_this_month += installation.marketplace_agent.price
        context['revenue_this_month'] = revenue_this_month
        
        # Average rating
        avg_rating = user_listings.aggregate(
            avg=models.Avg('rating_average')
        )['avg']
        context['average_rating'] = avg_rating or 0
        
        # Total reviews
        context['total_reviews'] = user_listings.aggregate(
            total=models.Sum('rating_count')
        )['total'] or 0
        
        # Status breakdown
        context['approved_count'] = user_listings.filter(status='approved').count()
        context['pending_count'] = user_listings.filter(status='pending').count()
        context['draft_count'] = user_listings.filter(status='draft').count()
        
        return context


class MarketplaceHomeView(LoginRequiredMixin, ListView):
    """Marketplace homepage with featured and popular agents"""
    model = MarketplaceAgent
    template_name = 'users/agents/marketplace/home.html'
    context_object_name = 'agents'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = MarketplaceAgent.objects.filter(status='approved')
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(tagline__icontains=search) |
                Q(tags__contains=[search])
            )
        
        # Category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Sorting
        sort = self.request.GET.get('sort', 'popular')
        if sort == 'popular':
            queryset = queryset.order_by('-install_count')
        elif sort == 'rating':
            queryset = queryset.order_by('-rating_average', '-rating_count')
        elif sort == 'newest':
            queryset = queryset.order_by('-published_at')
        elif sort == 'name':
            queryset = queryset.order_by('name')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['featured_agents'] = MarketplaceAgent.objects.filter(
            status='approved',
            is_featured=True
        )[:6]
        context['categories'] = MarketplaceAgent.Category.choices
        context['current_category'] = self.request.GET.get('category', '')
        context['current_sort'] = self.request.GET.get('sort', 'popular')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Stats
        context['total_agents'] = MarketplaceAgent.objects.filter(status='approved').count()
        context['total_installs'] = MarketplaceAgent.objects.filter(
            status='approved'
        ).aggregate(total=Count('installations'))['total'] or 0
        
        return context


class MarketplaceAgentDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of marketplace agent"""
    model = MarketplaceAgent
    template_name = 'agents/marketplace/detail.html'
    context_object_name = 'marketplace_agent'
    
    def get_queryset(self):
        return MarketplaceAgent.objects.filter(status='approved')
    
    def get_object(self):
        obj = super().get_object()
        # Increment view count
        obj.increment_views()
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user has installed
        if self.request.user.is_authenticated:
            context['is_installed'] = AgentInstallation.objects.filter(
                user=self.request.user,
                marketplace_agent=self.object,
                is_active=True
            ).exists()
            
            # Check if user has reviewed
            context['user_review'] = AgentReview.objects.filter(
                user=self.request.user,
                marketplace_agent=self.object
            ).first()
        else:
            context['is_installed'] = False
            context['user_review'] = None
        
        # Reviews
        context['reviews'] = self.object.reviews.filter(
            is_approved=True
        ).select_related('user').order_by('-helpful_count', '-created_at')[:10]
        
        # Rating distribution
        context['rating_distribution'] = self.object.get_rating_distribution()
        
        # Similar agents
        context['similar_agents'] = MarketplaceAgent.objects.filter(
            status='approved',
            category=self.object.category
        ).exclude(id=self.object.id)[:4]
        
        # Publisher's other agents
        context['publisher_agents'] = MarketplaceAgent.objects.filter(
            status='approved',
            publisher=self.object.publisher
        ).exclude(id=self.object.id)[:3]
        
        return context


class AgentInstallView(LoginRequiredMixin, View):
    """Install an agent from marketplace"""
    
    def post(self, request, pk):
        marketplace_agent = get_object_or_404(
            MarketplaceAgent,
            pk=pk,
            status='approved'
        )
        
        # Check if already installed
        existing = AgentInstallation.objects.filter(
            user=request.user,
            marketplace_agent=marketplace_agent,
            is_active=True
        ).first()
        
        if existing:
            messages.warning(request, 'You have already installed this agent.')
            return redirect('agents:marketplace-agent-detail', pk=pk)
        
        try:
            # Clone the agent
            original_agent = marketplace_agent.agent
            cloned_agent = Agent.objects.create(
                user=request.user,
                name=f"{marketplace_agent.name} (Installed)",
                description=original_agent.description,
                use_case=original_agent.use_case,
                prompt_template=original_agent.prompt_template,
                config_json=original_agent.config_json.copy(),
                is_active=True
            )
            
            # Create installation record
            installation = AgentInstallation.objects.create(
                user=request.user,
                marketplace_agent=marketplace_agent,
                installed_agent=cloned_agent
            )
            
            # Increment install count
            marketplace_agent.increment_installs()
            
            messages.success(
                request,
                f'Successfully installed "{marketplace_agent.name}"! You can now configure and use it.'
            )
            
            return redirect('agents:agent-detail', pk=cloned_agent.id)
            
        except Exception as e:
            messages.error(request, f'Failed to install agent: {str(e)}')
            return redirect('agents:marketplace-agent-detail', pk=pk)


class AgentUninstallView(LoginRequiredMixin, View):
    """Uninstall a marketplace agent"""
    
    def post(self, request, pk):
        installation = get_object_or_404(
            AgentInstallation,
            pk=pk,
            user=request.user
        )
        
        marketplace_agent = installation.marketplace_agent
        
        # Mark as uninstalled
        installation.uninstall()
        
        messages.success(
            request,
            f'"{marketplace_agent.name}" has been uninstalled.'
        )
        
        return redirect('agents:marketplace-my-installations')


# class MyInstallationsView(LoginRequiredMixin, ListView):
#     """View user's installed agents"""
#     model = AgentInstallation
#     template_name = 'users/agents/marketplace/my_installations.html'
#     context_object_name = 'installations'
#     paginate_by = 20
    
#     def get_queryset(self):
#         return AgentInstallation.objects.filter(
#             user=self.request.user,
#             is_active=True
#         ).select_related('marketplace_agent', 'installed_agent').order_by('-installed_at')

class MyInstallationsView(LoginRequiredMixin, ListView):
    """View user's installed agents"""
    model = AgentInstallation
    template_name = 'users/agents/marketplace/my_installations.html'
    context_object_name = 'installations'
    paginate_by = 20
    
    def get_queryset(self):
        return AgentInstallation.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related(
            'marketplace_agent', 
            'installed_agent'
        ).order_by('-installed_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all installations (not just paginated)
        all_installations = AgentInstallation.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('marketplace_agent', 'installed_agent')
        
        # Calculate stats
        context['total_installations'] = all_installations.count()
        
        # Recently used count (installations with last_used_at set)
        context['recently_used_count'] = all_installations.filter(
            last_used_at__isnull=False
        ).count()
        
        # Active agents count (installed agents that are active)
        context['active_agents_count'] = all_installations.filter(
            installed_agent__is_active=True
        ).count()
        
        return context


class PublishAgentView(LoginRequiredMixin, CreateView):
    """Publish an agent to marketplace"""
    model = MarketplaceAgent
    template_name = 'users/agents/marketplace/publish.html'
    fields = [
        'name', 'tagline', 'description', 'category', 'tags',
        'logo_url', 'screenshots', 'demo_video_url',
        'is_free', 'price',
        'documentation_url', 'support_url',
        'required_integrations', 'version'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get user's agents that aren't published
        context['user_agents'] = Agent.objects.filter(
            user=self.request.user
        ).exclude(
            marketplace_listing__isnull=False
        )
        return context
    
    def form_valid(self, form):
        agent_id = self.request.POST.get('agent_id')
        agent = get_object_or_404(Agent, id=agent_id, user=self.request.user)
        
        # Check if agent already published
        if hasattr(agent, 'marketplace_listing'):
            messages.error(self.request, 'This agent is already published.')
            return redirect('agents:agent-detail', pk=agent.id)
        
        form.instance.agent = agent
        form.instance.publisher = self.request.user
        form.instance.status = 'pending'
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            'Your agent has been submitted for review. You will be notified when it is approved.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:marketplace-my-listings')


class MyListingsView(LoginRequiredMixin, ListView):
    """View user's published agents"""
    model = MarketplaceAgent
    template_name = 'users/agents/marketplace/my_listings.html'
    context_object_name = 'listings'
    paginate_by = 20
    
    def get_queryset(self):
        return MarketplaceAgent.objects.filter(
            publisher=self.request.user
        ).order_by('-created_at')


class UpdateListingView(LoginRequiredMixin, UpdateView):
    """Update marketplace listing"""
    model = MarketplaceAgent
    template_name = 'agents/marketplace/update_listing.html'
    fields = [
        'name', 'tagline', 'description', 'category', 'tags',
        'logo_url', 'screenshots', 'demo_video_url',
        'is_free', 'price',
        'documentation_url', 'support_url', 'changelog',
        'required_integrations', 'version'
    ]
    
    def get_queryset(self):
        return MarketplaceAgent.objects.filter(publisher=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Listing updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('agents:marketplace-my-listings')


class CreateReviewView(LoginRequiredMixin, CreateView):
    """Create a review for marketplace agent"""
    model = AgentReview
    template_name = 'agents/marketplace/create_review.html'
    fields = ['rating', 'title', 'review_text']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.marketplace_agent = get_object_or_404(
            MarketplaceAgent,
            pk=self.kwargs['agent_id']
        )
        context['marketplace_agent'] = self.marketplace_agent
        
        # Check installation
        context['installation'] = AgentInstallation.objects.filter(
            user=self.request.user,
            marketplace_agent=self.marketplace_agent
        ).first()
        
        return context
    
    def form_valid(self, form):
        marketplace_agent = get_object_or_404(
            MarketplaceAgent,
            pk=self.kwargs['agent_id']
        )
        
        # Check if user already reviewed
        if AgentReview.objects.filter(
            user=self.request.user,
            marketplace_agent=marketplace_agent
        ).exists():
            messages.error(self.request, 'You have already reviewed this agent.')
            return redirect('agents:marketplace-agent-detail', pk=marketplace_agent.id)
        
        form.instance.user = self.request.user
        form.instance.marketplace_agent = marketplace_agent
        
        # Check if user has installed
        installation = AgentInstallation.objects.filter(
            user=self.request.user,
            marketplace_agent=marketplace_agent
        ).first()
        
        if installation:
            form.instance.installation = installation
            form.instance.is_verified = True
        
        response = super().form_valid(form)
        
        # Update marketplace agent rating
        marketplace_agent.update_rating(form.instance.rating)
        
        messages.success(self.request, 'Thank you for your review!')
        
        return response
    
    def get_success_url(self):
        return reverse_lazy(
            'agents:marketplace-agent-detail',
            kwargs={'pk': self.kwargs['agent_id']}
        )


class ReviewHelpfulnessView(LoginRequiredMixin, View):
    """Mark review as helpful or not"""
    
    def post(self, request, review_id):
        review = get_object_or_404(AgentReview, pk=review_id)
        is_helpful = request.POST.get('is_helpful') == 'true'
        
        # Check if user already voted
        existing_vote = ReviewHelpfulness.objects.filter(
            review=review,
            user=request.user
        ).first()
        
        if existing_vote:
            # Update vote
            if existing_vote.is_helpful != is_helpful:
                # Remove old vote count
                if existing_vote.is_helpful:
                    review.helpful_count -= 1
                else:
                    review.not_helpful_count -= 1
                
                # Add new vote count
                if is_helpful:
                    review.helpful_count += 1
                else:
                    review.not_helpful_count += 1
                
                existing_vote.is_helpful = is_helpful
                existing_vote.save()
                review.save()
        else:
            # Create new vote
            ReviewHelpfulness.objects.create(
                review=review,
                user=request.user,
                is_helpful=is_helpful
            )
            
            if is_helpful:
                review.helpful_count += 1
            else:
                review.not_helpful_count += 1
            review.save()
        
        return JsonResponse({
            'success': True,
            'helpful_count': review.helpful_count,
            'not_helpful_count': review.not_helpful_count
        })


class MarketplaceCategoryView(ListView):
    """Browse agents by category"""
    model = MarketplaceAgent
    template_name = 'agents/marketplace/category.html'
    context_object_name = 'agents'
    paginate_by = 12
    
    def get_queryset(self):
        self.category = self.kwargs['category']
        return MarketplaceAgent.objects.filter(
            status='approved',
            category=self.category
        ).order_by('-install_count')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['category_display'] = dict(MarketplaceAgent.Category.choices).get(self.category)
        return context
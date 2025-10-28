/**
 * AI Agent Platform - Embeddable Chat Widget Loader
 * 
 * This file should be saved as: embed/templates/embed/widget_loader.js
 * 
 * Usage:
 * <script src="https://yourdomain.com/embed/loader/{{ agent.id }}/" async></script>
 * <script>
 *   window.AIAgentWidget = {
 *     agentId: '{{ agent.id }}',
 *     theme: 'light',
 *     primaryColor: '#4F46E5',
 *     position: 'right',
 *     greeting: 'Hi! Need help?'
 *   };
 * </script>
 */

(function() {
    'use strict';

    // Configuration
    const config = window.AIAgentWidget || {};
    const agentId = config.agentId || '{{ agent.id }}';
    const theme = config.theme || 'light';
    const primaryColor = config.primaryColor || '#4F46E5';
    const position = config.position || 'right';
    const greeting = config.greeting || '{{ agent.name }}';
    const baseUrl = '{{ request.scheme }}://{{ request.get_host }}';

    // Prevent double initialization
    if (window.__aiAgentWidgetLoaded) {
        console.warn('AI Agent Widget already loaded');
        return;
    }
    window.__aiAgentWidgetLoaded = true;

    // Widget state
    let isOpen = false;
    let unreadCount = 0;

    // Create widget elements
    function createWidget() {
        // Create container
        const container = document.createElement('div');
        container.id = 'ai-agent-widget-container';
        container.style.cssText = `
            position: fixed;
            bottom: 20px;
            ${position === 'left' ? 'left: 20px;' : 'right: 20px;'}
            z-index: 999999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;

        // Create chat window (initially hidden)
        const chatWindow = document.createElement('div');
        chatWindow.id = 'ai-agent-chat-window';
        chatWindow.style.cssText = `
            position: fixed;
            bottom: 90px;
            ${position === 'left' ? 'left: 20px;' : 'right: 20px;'}
            width: 400px;
            height: 600px;
            max-height: calc(100vh - 120px);
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
            overflow: hidden;
            display: none;
            background: white;
            z-index: 999998;
        `;

        // Create iframe for chat
        const iframe = document.createElement('iframe');
        iframe.id = 'ai-agent-chat-iframe';
        iframe.src = `${baseUrl}/embed/chat/${agentId}/?theme=${theme}&color=${encodeURIComponent(primaryColor)}`;
        iframe.style.cssText = `
            width: 100%;
            height: 100%;
            border: none;
        `;
        iframe.allow = 'clipboard-write';
        chatWindow.appendChild(iframe);

        // Create toggle button
        const button = document.createElement('button');
        button.id = 'ai-agent-widget-button';
        button.setAttribute('aria-label', 'Open chat');
        button.style.cssText = `
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: none;
            background: ${primaryColor};
            color: white;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            position: relative;
        `;

        // Button content (SVG icons)
        const chatIcon = `
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
        `;

        const closeIcon = `
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        `;

        button.innerHTML = chatIcon;

        // Badge for unread messages
        const badge = document.createElement('div');
        badge.id = 'ai-agent-widget-badge';
        badge.style.cssText = `
            position: absolute;
            top: -5px;
            right: -5px;
            background: #EF4444;
            color: white;
            border-radius: 10px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: bold;
            display: none;
            min-width: 20px;
            text-align: center;
        `;
        button.appendChild(badge);

        // Hover effect
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = `0 6px 20px ${primaryColor}66`;
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
        });

        // Toggle chat
        button.addEventListener('click', function() {
            toggleChat();
        });

        // Assemble widget
        container.appendChild(button);
        document.body.appendChild(chatWindow);
        document.body.appendChild(container);

        // Add entry animation
        setTimeout(() => {
            container.style.animation = 'slideInUp 0.4s ease';
        }, 100);

        // Show greeting tooltip after 2 seconds
        if (!isOpen) {
            setTimeout(showGreeting, 2000);
        }
    }

    // Toggle chat window
    function toggleChat() {
        isOpen = !isOpen;
        const chatWindow = document.getElementById('ai-agent-chat-window');
        const button = document.getElementById('ai-agent-widget-button');
        const badge = document.getElementById('ai-agent-widget-badge');

        if (isOpen) {
            chatWindow.style.display = 'block';
            chatWindow.style.animation = 'slideInUp 0.3s ease';
            button.innerHTML = `
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            `;
            button.appendChild(badge);
            button.setAttribute('aria-label', 'Close chat');
            
            // Clear unread count
            unreadCount = 0;
            updateBadge();
            
            // Remove greeting
            const greeting = document.getElementById('ai-agent-greeting');
            if (greeting) greeting.remove();
        } else {
            chatWindow.style.display = 'none';
            button.innerHTML = `
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
            `;
            button.appendChild(badge);
            button.setAttribute('aria-label', 'Open chat');
        }
    }

    // Show greeting tooltip
    function showGreeting() {
        if (isOpen) return;

        const existing = document.getElementById('ai-agent-greeting');
        if (existing) return;

        const tooltip = document.createElement('div');
        tooltip.id = 'ai-agent-greeting';
        tooltip.style.cssText = `
            position: fixed;
            bottom: 90px;
            ${position === 'left' ? 'left: 20px;' : 'right: 20px;'}
            background: white;
            color: #1f2937;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 999997;
            max-width: 250px;
            animation: slideInUp 0.3s ease;
        `;

        tooltip.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 14px; font-weight: 500;">${greeting}</span>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="border: none; background: none; cursor: pointer; padding: 4px; color: #9ca3af; font-size: 18px; line-height: 1;">
                    ×
                </button>
            </div>
        `;

        document.body.appendChild(tooltip);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (tooltip.parentElement) {
                tooltip.style.animation = 'slideOutDown 0.3s ease';
                setTimeout(() => tooltip.remove(), 300);
            }
        }, 5000);
    }

    // Update unread badge
    function updateBadge() {
        const badge = document.getElementById('ai-agent-widget-badge');
        if (!badge) return;

        if (unreadCount > 0 && !isOpen) {
            badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }

    // Listen for messages from iframe
    window.addEventListener('message', function(event) {
        // Verify origin for security
        if (event.origin !== baseUrl) return;

        const data = event.data;
        if (data.type === 'close-widget') {
            toggleChat();
        } else if (data.type === 'new-message' && !isOpen) {
            unreadCount++;
            updateBadge();
        }
    });

    // Add animations CSS
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes slideOutDown {
            from {
                opacity: 1;
                transform: translateY(0);
            }
            to {
                opacity: 0;
                transform: translateY(20px);
            }
        }
    `;
    document.head.appendChild(style);

    // Initialize widget when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createWidget);
    } else {
        createWidget();
    }

    // Public API
    window.AIAgentWidgetAPI = {
        open: function() {
            if (!isOpen) toggleChat();
        },
        close: function() {
            if (isOpen) toggleChat();
        },
        toggle: toggleChat,
        isOpen: function() {
            return isOpen;
        }
    };

    console.log('AI Agent Widget loaded for agent:', agentId);
})();
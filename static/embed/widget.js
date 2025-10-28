/**
 * AI Agent Platform - Embeddable Chat Widget
 * Phase 7: Integration Layer & Embeddability
 * 
 * Usage:
 * <script src="https://your-domain.com/static/embed/widget.js"></script>
 * <script>
 *   AIAgentWidget.init({
 *     agentId: '123',
 *     apiKey: 'your-api-key',
 *     position: 'bottom-right', // or 'bottom-left'
 *     theme: 'light', // or 'dark'
 *     primaryColor: '#4F46E5',
 *     title: 'Chat with us'
 *   });
 * </script>
 */

(function() {
    'use strict';
    
    // Prevent multiple initializations
    if (window.AIAgentWidget) {
        return;
    }
    
    // Default configuration
    const DEFAULT_CONFIG = {
        position: 'bottom-right',
        theme: 'light',
        primaryColor: '#4F46E5',
        title: 'Chat with us',
        subtitle: 'We\'re here to help',
        placeholder: 'Type your message...',
        welcomeMessage: null,
        showTimestamp: true,
        soundEnabled: true,
        width: '400px',
        height: '600px',
        zIndex: 10000,
        launcherSize: '60px'
    };
    
    class AIAgentWidget {
        constructor(config) {
            this.config = { ...DEFAULT_CONFIG, ...config };
            this.isOpen = false;
            this.conversationId = null;
            this.ws = null;
            this.messageQueue = [];
            
            if (!this.config.agentId) {
                throw new Error('agentId is required');
            }
            
            this.init();
        }
        
        init() {
            this.injectStyles();
            this.createWidget();
            this.attachEventListeners();
            
            // Load conversation from localStorage if exists
            this.loadConversation();
        }
        
        injectStyles() {
            const styles = `
                .aap-widget-container {
                    position: fixed;
                    ${this.config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
                    bottom: 20px;
                    z-index: ${this.config.zIndex};
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }
                
                .aap-widget-launcher {
                    width: ${this.config.launcherSize};
                    height: ${this.config.launcherSize};
                    border-radius: 50%;
                    background-color: ${this.config.primaryColor};
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                
                .aap-widget-launcher:hover {
                    transform: scale(1.1);
                    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
                }
                
                .aap-widget-launcher svg {
                    width: 28px;
                    height: 28px;
                }
                
                .aap-widget-window {
                    position: absolute;
                    bottom: 80px;
                    ${this.config.position.includes('right') ? 'right: 0;' : 'left: 0;'}
                    width: ${this.config.width};
                    height: ${this.config.height};
                    max-width: calc(100vw - 40px);
                    max-height: calc(100vh - 120px);
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
                    display: flex;
                    flex-direction: column;
                    opacity: 0;
                    transform: scale(0.9) translateY(20px);
                    transition: opacity 0.2s, transform 0.2s;
                    pointer-events: none;
                }
                
                .aap-widget-window.open {
                    opacity: 1;
                    transform: scale(1) translateY(0);
                    pointer-events: all;
                }
                
                .aap-widget-header {
                    background: ${this.config.primaryColor};
                    color: white;
                    padding: 16px 20px;
                    border-radius: 16px 16px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .aap-widget-header-title {
                    flex: 1;
                }
                
                .aap-widget-header-title h3 {
                    margin: 0;
                    font-size: 16px;
                    font-weight: 600;
                }
                
                .aap-widget-header-title p {
                    margin: 4px 0 0 0;
                    font-size: 13px;
                    opacity: 0.9;
                }
                
                .aap-widget-close {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    padding: 4px;
                    display: flex;
                    align-items: center;
                    opacity: 0.8;
                    transition: opacity 0.2s;
                }
                
                .aap-widget-close:hover {
                    opacity: 1;
                }
                
                .aap-widget-messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    background: #f9fafb;
                }
                
                .aap-message {
                    margin-bottom: 16px;
                    display: flex;
                    gap: 8px;
                }
                
                .aap-message-user {
                    justify-content: flex-end;
                }
                
                .aap-message-bubble {
                    max-width: 80%;
                    padding: 10px 14px;
                    border-radius: 16px;
                    font-size: 14px;
                    line-height: 1.5;
                }
                
                .aap-message-assistant .aap-message-bubble {
                    background: white;
                    color: #1f2937;
                    border: 1px solid #e5e7eb;
                    border-bottom-left-radius: 4px;
                }
                
                .aap-message-user .aap-message-bubble {
                    background: ${this.config.primaryColor};
                    color: white;
                    border-bottom-right-radius: 4px;
                }
                
                .aap-message-timestamp {
                    font-size: 11px;
                    color: #9ca3af;
                    margin-top: 4px;
                }
                
                .aap-typing-indicator {
                    display: flex;
                    gap: 4px;
                    padding: 10px 14px;
                    background: white;
                    border-radius: 16px;
                    border: 1px solid #e5e7eb;
                    width: fit-content;
                }
                
                .aap-typing-dot {
                    width: 8px;
                    height: 8px;
                    background: #9ca3af;
                    border-radius: 50%;
                    animation: typing 1.4s infinite;
                }
                
                .aap-typing-dot:nth-child(2) {
                    animation-delay: 0.2s;
                }
                
                .aap-typing-dot:nth-child(3) {
                    animation-delay: 0.4s;
                }
                
                @keyframes typing {
                    0%, 60%, 100% {
                        transform: translateY(0);
                        opacity: 0.7;
                    }
                    30% {
                        transform: translateY(-8px);
                        opacity: 1;
                    }
                }
                
                .aap-widget-input-container {
                    padding: 16px 20px;
                    background: white;
                    border-top: 1px solid #e5e7eb;
                    border-radius: 0 0 16px 16px;
                }
                
                .aap-widget-input-form {
                    display: flex;
                    gap: 8px;
                }
                
                .aap-widget-input {
                    flex: 1;
                    padding: 10px 14px;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.2s;
                }
                
                .aap-widget-input:focus {
                    border-color: ${this.config.primaryColor};
                }
                
                .aap-widget-send-btn {
                    background: ${this.config.primaryColor};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 16px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: opacity 0.2s;
                }
                
                .aap-widget-send-btn:hover {
                    opacity: 0.9;
                }
                
                .aap-widget-send-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                
                .aap-powered-by {
                    text-align: center;
                    font-size: 11px;
                    color: #9ca3af;
                    margin-top: 8px;
                }
                
                .aap-powered-by a {
                    color: ${this.config.primaryColor};
                    text-decoration: none;
                }
            `;
            
            const styleEl = document.createElement('style');
            styleEl.textContent = styles;
            document.head.appendChild(styleEl);
        }
        
        createWidget() {
            const container = document.createElement('div');
            container.className = 'aap-widget-container';
            container.innerHTML = `
                <div class="aap-widget-launcher" id="aap-launcher">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
                    </svg>
                </div>
                
                <div class="aap-widget-window" id="aap-widget-window">
                    <div class="aap-widget-header">
                        <div class="aap-widget-header-title">
                            <h3>${this.config.title}</h3>
                            <p>${this.config.subtitle}</p>
                        </div>
                        <button class="aap-widget-close" id="aap-close">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                    
                    <div class="aap-widget-messages" id="aap-messages"></div>
                    
                    <div class="aap-widget-input-container">
                        <form class="aap-widget-input-form" id="aap-form">
                            <input 
                                type="text" 
                                class="aap-widget-input" 
                                id="aap-input"
                                placeholder="${this.config.placeholder}"
                                autocomplete="off"
                            />
                            <button type="submit" class="aap-widget-send-btn" id="aap-send">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                        </form>
                        <div class="aap-powered-by">
                            Powered by <a href="https://your-domain.com" target="_blank">AI Agent Platform</a>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(container);
            
            this.elements = {
                launcher: document.getElementById('aap-launcher'),
                window: document.getElementById('aap-widget-window'),
                close: document.getElementById('aap-close'),
                messages: document.getElementById('aap-messages'),
                form: document.getElementById('aap-form'),
                input: document.getElementById('aap-input'),
                send: document.getElementById('aap-send')
            };
        }
        
        attachEventListeners() {
            this.elements.launcher.addEventListener('click', () => this.toggle());
            this.elements.close.addEventListener('click', () => this.close());
            this.elements.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
        
        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }
        
        open() {
            this.isOpen = true;
            this.elements.window.classList.add('open');
            this.elements.input.focus();
            
            // Show welcome message if configured and no messages
            if (this.config.welcomeMessage && this.elements.messages.children.length === 0) {
                this.addMessage('assistant', this.config.welcomeMessage);
            }
        }
        
        close() {
            this.isOpen = false;
            this.elements.window.classList.remove('open');
        }
        
        addMessage(role, content, timestamp = new Date()) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `aap-message aap-message-${role}`;
            
            let timestampHtml = '';
            if (this.config.showTimestamp) {
                const timeStr = timestamp.toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                timestampHtml = `<div class="aap-message-timestamp">${timeStr}</div>`;
            }
            
            messageDiv.innerHTML = `
                <div>
                    <div class="aap-message-bubble">${this.escapeHtml(content)}</div>
                    ${timestampHtml}
                </div>
            `;
            
            this.elements.messages.appendChild(messageDiv);
            this.scrollToBottom();
            
            // Save to localStorage
            this.saveMessage(role, content, timestamp);
        }
        
        showTyping() {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'aap-message aap-message-assistant';
            typingDiv.id = 'aap-typing';
            typingDiv.innerHTML = `
                <div class="aap-typing-indicator">
                    <div class="aap-typing-dot"></div>
                    <div class="aap-typing-dot"></div>
                    <div class="aap-typing-dot"></div>
                </div>
            `;
            
            this.elements.messages.appendChild(typingDiv);
            this.scrollToBottom();
        }
        
        hideTyping() {
            const typing = document.getElementById('aap-typing');
            if (typing) {
                typing.remove();
            }
        }
        
        async sendMessage() {
            const message = this.elements.input.value.trim();
            if (!message) return;
            
            // Add user message
            this.addMessage('user', message);
            this.elements.input.value = '';
            this.elements.send.disabled = true;
            
            // Show typing indicator
            this.showTyping();
            
            try {
                const response = await this.callAPI(message);
                
                this.hideTyping();
                
                if (response.response) {
                    this.addMessage('assistant', response.response);
                    
                    // Save conversation ID
                    if (response.conversation_id) {
                        this.conversationId = response.conversation_id;
                        localStorage.setItem(
                            `aap_conversation_${this.config.agentId}`,
                            response.conversation_id
                        );
                    }
                } else {
                    this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
                }
            } catch (error) {
                console.error('Chat error:', error);
                this.hideTyping();
                this.addMessage('assistant', 'Sorry, I\'m having trouble connecting. Please try again.');
            } finally {
                this.elements.send.disabled = false;
                this.elements.input.focus();
            }
        }
        
        async callAPI(message) {
            const url = `${this.config.apiUrl || window.location.origin}/api/agents/${this.config.agentId}/chat/`;
            
            const headers = {
                'Content-Type': 'application/json'
            };
            
            if (this.config.apiKey) {
                headers['X-API-Key'] = this.config.apiKey;
            }
            
            const body = {
                message: message
            };
            
            if (this.conversationId) {
                body.conversation_id = this.conversationId;
            }
            
            const response = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        }
        
        scrollToBottom() {
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
        }
        
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        saveMessage(role, content, timestamp) {
            const messages = this.getMessages();
            messages.push({ role, content, timestamp: timestamp.toISOString() });
            
            // Keep last 50 messages
            if (messages.length > 50) {
                messages.shift();
            }
            
            localStorage.setItem(
                `aap_messages_${this.config.agentId}`,
                JSON.stringify(messages)
            );
        }
        
        getMessages() {
            const stored = localStorage.getItem(`aap_messages_${this.config.agentId}`);
            return stored ? JSON.parse(stored) : [];
        }
        
        loadConversation() {
            // Load conversation ID
            const conversationId = localStorage.getItem(
                `aap_conversation_${this.config.agentId}`
            );
            if (conversationId) {
                this.conversationId = parseInt(conversationId);
            }
            
            // Load messages
            const messages = this.getMessages();
            messages.forEach(msg => {
                this.addMessage(msg.role, msg.content, new Date(msg.timestamp));
            });
        }
    }
    
    // Expose global API
    window.AIAgentWidget = {
        init: function(config) {
            return new AIAgentWidget(config);
        }
    };
})();
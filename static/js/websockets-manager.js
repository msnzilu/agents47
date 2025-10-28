/**
 * WebSocket Manager for AI Agent Platform
 * Phase 4: Real-Time Chat & WebSockets
 * 
 * Reusable WebSocket connection manager for all chat interfaces
 */

class WebSocketManager {
    constructor(conversationId, options = {}) {
        this.conversationId = conversationId;
        this.options = {
            maxReconnectAttempts: options.maxReconnectAttempts || 5,
            reconnectDelay: options.reconnectDelay || 1000,
            pingInterval: options.pingInterval || 30000,
            onConnect: options.onConnect || null,
            onDisconnect: options.onDisconnect || null,
            onMessage: options.onMessage || null,
            onError: options.onError || null,
            onStreamStart: options.onStreamStart || null,
            onStreamToken: options.onStreamToken || null,
            onStreamEnd: options.onStreamEnd || null,
            onTyping: options.onTyping || null,
        };
        
        // State
        this.socket = null;
        this.reconnectAttempts = 0;
        this.reconnectTimeout = null;
        this.pingInterval = null;
        this.isConnecting = false;
        this.isManualClose = false;
        
        // Build WebSocket URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.wsUrl = `${protocol}//${window.location.host}/ws/chat/${conversationId}/`;
        
        console.log(`[WebSocket] Initialized for conversation ${conversationId}`);
    }
    
    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.isConnecting || (this.socket && this.socket.readyState === WebSocket.OPEN)) {
            console.log('[WebSocket] Already connected or connecting');
            return;
        }
        
        this.isConnecting = true;
        this.isManualClose = false;
        
        console.log(`[WebSocket] Connecting to: ${this.wsUrl}`);
        
        try {
            this.socket = new WebSocket(this.wsUrl);
            
            this.socket.onopen = (event) => this.handleOpen(event);
            this.socket.onmessage = (event) => this.handleMessage(event);
            this.socket.onerror = (event) => this.handleError(event);
            this.socket.onclose = (event) => this.handleClose(event);
            
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.isConnecting = false;
            if (this.options.onError) {
                this.options.onError(error);
            }
        }
    }
    
    /**
     * Handle WebSocket open event
     */
    handleOpen(event) {
        console.log('[WebSocket] Connection established');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        
        // Start ping interval
        this.startPingInterval();
        
        // Call user callback
        if (this.options.onConnect) {
            this.options.onConnect(event);
        }
    }
    
    /**
     * Handle incoming messages
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('[WebSocket] Received:', data.type, data);
            
            // Route message to appropriate handler
            switch (data.type) {
                case 'connection_established':
                    console.log('[WebSocket] Connection confirmed for conversation:', data.conversation_id);
                    break;
                    
                case 'message':
                case 'message_sent':
                    if (this.options.onMessage) {
                        this.options.onMessage(data);
                    }
                    break;
                    
                case 'stream_start':
                    if (this.options.onStreamStart) {
                        this.options.onStreamStart(data);
                    }
                    break;
                    
                case 'stream_token':
                    if (this.options.onStreamToken) {
                        this.options.onStreamToken(data);
                    }
                    break;
                    
                case 'stream_end':
                    if (this.options.onStreamEnd) {
                        this.options.onStreamEnd(data);
                    }
                    break;
                    
                case 'agent_typing':
                case 'user_typing':
                    if (this.options.onTyping) {
                        this.options.onTyping(data);
                    }
                    break;
                    
                case 'error':
                    console.error('[WebSocket] Server error:', data.error);
                    if (this.options.onError) {
                        this.options.onError(new Error(data.error));
                    }
                    break;
                    
                case 'pong':
                    // Keep-alive response
                    break;
                    
                default:
                    console.warn('[WebSocket] Unknown message type:', data.type);
            }
            
        } catch (error) {
            console.error('[WebSocket] Error parsing message:', error);
        }
    }
    
    /**
     * Handle WebSocket errors
     */
    handleError(event) {
        console.error('[WebSocket] Error occurred:', event);
        if (this.options.onError) {
            this.options.onError(event);
        }
    }
    
    /**
     * Handle WebSocket close event
     */
    handleClose(event) {
        console.log('[WebSocket] Connection closed:', event.code, event.reason);
        this.isConnecting = false;
        
        // Stop ping interval
        this.stopPingInterval();
        
        // Call user callback
        if (this.options.onDisconnect) {
            this.options.onDisconnect(event);
        }
        
        // Attempt reconnection if not manually closed
        if (!this.isManualClose && this.reconnectAttempts < this.options.maxReconnectAttempts) {
            this.reconnect();
        } else if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.error('[WebSocket] Max reconnection attempts reached');
        }
    }
    
    /**
     * Reconnect to WebSocket
     */
    reconnect() {
        this.reconnectAttempts++;
        const delay = Math.min(
            this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            30000
        );
        
        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    /**
     * Send message through WebSocket
     */
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            console.log('[WebSocket] Sending:', data);
            this.socket.send(message);
            return true;
        } else {
            console.warn('[WebSocket] Cannot send - not connected');
            return false;
        }
    }
    
    /**
     * Send chat message
     */
    sendMessage(content, tempId = null) {
        return this.send({
            type: 'chat_message',
            message: content,
            temp_id: tempId || `temp-${Date.now()}`
        });
    }
    
    /**
     * Send typing indicator
     */
    sendTyping(isTyping) {
        return this.send({
            type: 'typing',
            is_typing: isTyping
        });
    }
    
    /**
     * Send ping
     */
    sendPing() {
        return this.send({
            type: 'ping'
        });
    }
    
    /**
     * Start ping interval
     */
    startPingInterval() {
        this.stopPingInterval();
        this.pingInterval = setInterval(() => {
            this.sendPing();
        }, this.options.pingInterval);
    }
    
    /**
     * Stop ping interval
     */
    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    /**
     * Disconnect WebSocket
     */
    disconnect() {
        console.log('[WebSocket] Manually disconnecting');
        this.isManualClose = true;
        this.stopPingInterval();
        
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }
        
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
    
    /**
     * Check if connected
     */
    isConnected() {
        return this.socket && this.socket.readyState === WebSocket.OPEN;
    }
    
    /**
     * Get connection state
     */
    getState() {
        if (!this.socket) return 'DISCONNECTED';
        
        switch (this.socket.readyState) {
            case WebSocket.CONNECTING:
                return 'CONNECTING';
            case WebSocket.OPEN:
                return 'CONNECTED';
            case WebSocket.CLOSING:
                return 'CLOSING';
            case WebSocket.CLOSED:
                return 'DISCONNECTED';
            default:
                return 'UNKNOWN';
        }
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketManager;
}
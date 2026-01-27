/**
 * WebSocket Client with Automatic Reconnection
 * Production-ready client for Django Channels WebSocket connections
 * 
 * Features:
 * - Exponential backoff reconnection
 * - Automatic reconnect on disconnect
 * - Event-based message handling
 * - Connection state management
 * - Ping/pong heartbeat support
 * 
 * @author Brandon Trigueros Lara
 * @date January 27, 2026
 */

class WebSocketClient {
    constructor(url, options = {}) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.maxReconnectDelay = options.maxReconnectDelay || 30000;
        this.heartbeatInterval = options.heartbeatInterval || 30000;
        this.heartbeatTimer = null;
        this.shouldReconnect = true;
        this.isConnecting = false;
        
        // Event handlers
        this.onOpenHandlers = [];
        this.onCloseHandlers = [];
        this.onMessageHandlers = [];
        this.onErrorHandlers = [];
        this.onStateChangeHandlers = [];
        
        // State
        this.state = 'disconnected'; // disconnected, connecting, connected, reconnecting
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.isConnecting || this.state === 'connected') {
            console.log('Already connected or connecting');
            return;
        }

        this.isConnecting = true;
        this.setState('connecting');

        try {
            // Construct WebSocket URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const wsUrl = `${protocol}//${host}${this.url}`;
            
            console.log(`[WebSocket] Connecting to ${wsUrl}...`);
            this.ws = new WebSocket(wsUrl);

            // Event listeners
            this.ws.onopen = this._handleOpen.bind(this);
            this.ws.onclose = this._handleClose.bind(this);
            this.ws.onmessage = this._handleMessage.bind(this);
            this.ws.onerror = this._handleError.bind(this);
            
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.isConnecting = false;
            this._scheduleReconnect();
        }
    }

    /**
     * Disconnect from WebSocket server
     * @param {boolean} shouldReconnect - Whether to allow automatic reconnection
     */
    disconnect(shouldReconnect = false) {
        this.shouldReconnect = shouldReconnect;
        
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.setState('disconnected');
    }

    /**
     * Send message to server
     * @param {Object} message - Message object to send
     */
    send(message) {
        if (this.state !== 'connected') {
            console.warn('[WebSocket] Not connected. Message not sent:', message);
            return false;
        }

        try {
            const jsonMessage = JSON.stringify(message);
            this.ws.send(jsonMessage);
            console.log('[WebSocket] Message sent:', message);
            return true;
        } catch (error) {
            console.error('[WebSocket] Error sending message:', error);
            return false;
        }
    }

    /**
     * Register event handler
     * @param {string} event - Event name (open, close, message, error, statechange)
     * @param {Function} handler - Handler function
     */
    on(event, handler) {
        switch (event) {
            case 'open':
                this.onOpenHandlers.push(handler);
                break;
            case 'close':
                this.onCloseHandlers.push(handler);
                break;
            case 'message':
                this.onMessageHandlers.push(handler);
                break;
            case 'error':
                this.onErrorHandlers.push(handler);
                break;
            case 'statechange':
                this.onStateChangeHandlers.push(handler);
                break;
        }
    }

    /**
     * Internal: Handle WebSocket open event
     */
    _handleOpen(event) {
        console.log('[WebSocket] Connected successfully');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.setState('connected');

        // Start heartbeat
        this._startHeartbeat();

        // Call registered handlers
        this.onOpenHandlers.forEach(handler => handler(event));
    }

    /**
     * Internal: Handle WebSocket close event
     */
    _handleClose(event) {
        console.log(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason})`);
        this.isConnecting = false;

        // Stop heartbeat
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }

        // Call registered handlers
        this.onCloseHandlers.forEach(handler => handler(event));

        // Schedule reconnection if needed
        if (this.shouldReconnect && event.code !== 1000) { // 1000 = normal closure
            this._scheduleReconnect();
        } else {
            this.setState('disconnected');
        }
    }

    /**
     * Internal: Handle WebSocket message event
     */
    _handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('[WebSocket] Message received:', data);

            // Call registered handlers
            this.onMessageHandlers.forEach(handler => handler(data));
        } catch (error) {
            console.error('[WebSocket] Error parsing message:', error);
        }
    }

    /**
     * Internal: Handle WebSocket error event
     */
    _handleError(event) {
        console.error('[WebSocket] Error:', event);
        this.onErrorHandlers.forEach(handler => handler(event));
    }

    /**
     * Internal: Schedule reconnection with exponential backoff
     */
    _scheduleReconnect() {
        if (!this.shouldReconnect) {
            return;
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[WebSocket] Max reconnection attempts reached');
            this.setState('disconnected');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.setState('reconnecting');

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Internal: Start heartbeat to keep connection alive
     */
    _startHeartbeat() {
        if (this.heartbeatInterval <= 0) {
            return;
        }

        this.heartbeatTimer = setInterval(() => {
            if (this.state === 'connected') {
                this.send({ type: 'ping' });
            }
        }, this.heartbeatInterval);
    }

    /**
     * Internal: Set connection state
     */
    setState(newState) {
        const oldState = this.state;
        this.state = newState;
        console.log(`[WebSocket] State: ${oldState} → ${newState}`);
        
        this.onStateChangeHandlers.forEach(handler => handler(newState, oldState));
    }

    /**
     * Get current connection state
     */
    getState() {
        return this.state;
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.state === 'connected';
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketClient;
}

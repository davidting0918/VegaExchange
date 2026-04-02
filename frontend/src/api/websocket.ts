/**
 * WebSocket connection manager for real-time market data.
 *
 * Connects to the backend at /api/ws, supports channel-based pub/sub,
 * JWT auth, and auto-reconnect with exponential backoff.
 */

type MessageHandler = (msg: { channel: string; data: unknown }) => void

interface PendingAction {
  action: 'subscribe' | 'unsubscribe'
  channel: string
}

class WebSocketManager {
  private ws: WebSocket | null = null
  private url: string
  private token: string | null = null
  private listeners = new Map<string, Set<MessageHandler>>()
  private subscribedChannels = new Set<string>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private intentionallyClosed = false
  private pendingActions: PendingAction[] = []
  private statusListeners = new Set<(connected: boolean) => void>()

  constructor() {
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const wsProtocol = apiBase.startsWith('https') ? 'wss' : 'ws'
    const host = apiBase.replace(/^https?:\/\//, '')
    this.url = `${wsProtocol}://${host}/api/ws`

    // Pause on tab hidden, reconnect on visible
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          this.disconnect()
        } else if (this.subscribedChannels.size > 0) {
          this.connect()
        }
      })
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  setToken(token: string | null) {
    this.token = token
  }

  onStatusChange(cb: (connected: boolean) => void): () => void {
    this.statusListeners.add(cb)
    return () => this.statusListeners.delete(cb)
  }

  private notifyStatus(connected: boolean) {
    this.statusListeners.forEach((cb) => cb(connected))
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    this.intentionallyClosed = false
    // Read token from localStorage if not explicitly set
    const token = this.token || localStorage.getItem('vega_access_token')
    const urlWithAuth = token ? `${this.url}?token=${token}` : this.url

    try {
      this.ws = new WebSocket(urlWithAuth)
    } catch {
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.reconnectDelay = 1000
      this.notifyStatus(true)

      // Re-subscribe to all channels
      for (const channel of this.subscribedChannels) {
        this.sendSubscribe(channel)
      }

      // Flush pending actions
      for (const action of this.pendingActions) {
        if (action.action === 'subscribe') this.sendSubscribe(action.channel)
        else this.sendUnsubscribe(action.channel)
      }
      this.pendingActions = []
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        // Handle heartbeat
        if (msg.type === 'ping') {
          this.ws?.send(JSON.stringify({ action: 'pong' }))
          return
        }

        // Handle subscription confirmations
        if (msg.type === 'subscribed' || msg.type === 'unsubscribed' || msg.type === 'error') {
          return
        }

        // Broadcast to channel listeners
        if (msg.channel) {
          const handlers = this.listeners.get(msg.channel)
          if (handlers) {
            handlers.forEach((handler) => handler(msg))
          }
        }
      } catch {
        // Ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      this.notifyStatus(false)
      if (!this.intentionallyClosed) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      // onclose will fire after onerror
    }
  }

  disconnect() {
    this.intentionallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.notifyStatus(false)
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      this.connect()
    }, this.reconnectDelay)
  }

  private sendSubscribe(channel: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', channel }))
    }
  }

  private sendUnsubscribe(channel: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'unsubscribe', channel }))
    }
  }

  subscribe(channel: string, handler: MessageHandler) {
    // Track handler
    if (!this.listeners.has(channel)) {
      this.listeners.set(channel, new Set())
    }
    this.listeners.get(channel)!.add(handler)

    // Track channel subscription
    if (!this.subscribedChannels.has(channel)) {
      this.subscribedChannels.add(channel)
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.sendSubscribe(channel)
      } else {
        this.pendingActions.push({ action: 'subscribe', channel })
        this.connect()
      }
    }
  }

  unsubscribe(channel: string, handler: MessageHandler) {
    const handlers = this.listeners.get(channel)
    if (handlers) {
      handlers.delete(handler)
      if (handlers.size === 0) {
        this.listeners.delete(channel)
        this.subscribedChannels.delete(channel)
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.sendUnsubscribe(channel)
        }

        // Disconnect if no more subscriptions
        if (this.subscribedChannels.size === 0) {
          this.disconnect()
        }
      }
    }
  }
}

// Singleton
export const wsManager = new WebSocketManager()

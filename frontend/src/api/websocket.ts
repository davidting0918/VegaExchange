/**
 * Single WebSocket connection for real-time updates.
 * Subscriptions: pool:{symbol}, user, orderbook:{symbol}.
 * Reconnects with exponential backoff and re-subscribes on reconnect.
 */

export type WsMessage = {
  channel: string
  symbol?: string
  data: unknown
}

type Subscription = { channel: string; symbol?: string }

const DEFAULT_WS_RECONNECT_INITIAL_MS = 1000
const DEFAULT_WS_RECONNECT_MAX_MS = 30000

function getWsUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const url = base.replace(/^http/, 'ws')
  return `${url}/ws`
}

class WebSocketService {
  private ws: WebSocket | null = null
  private url: string = getWsUrl()
  private token: string | null = null
  private messageHandler: ((msg: WsMessage) => void) | null = null
  private subscriptions = new Set<string>()
  private subscriptionList: Subscription[] = []
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private closed = false
  private closeWhenOpen = false

  setToken(token: string | null) {
    this.token = token
  }

  getConnectionUrl(): string {
    if (this.token) {
      const sep = this.url.includes('?') ? '&' : '?'
      return `${this.url}${sep}token=${encodeURIComponent(this.token)}`
    }
    return this.url
  }

  setMessageHandler(handler: ((msg: WsMessage) => void) | null) {
    this.messageHandler = handler
  }

  private subKey(channel: string, symbol?: string): string {
    return symbol ? `${channel}:${symbol}` : channel
  }

  subscribe(channel: string, symbol?: string): void {
    const key = this.subKey(channel, symbol)
    if (this.subscriptions.has(key)) return
    this.subscriptions.add(key)
    this.subscriptionList.push({ channel, symbol })
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendSubscribe(channel, symbol)
    }
  }

  unsubscribe(channel: string, symbol?: string): void {
    const key = this.subKey(channel, symbol)
    this.subscriptions.delete(key)
    this.subscriptionList = this.subscriptionList.filter(
      (s) => s.channel !== channel || (symbol != null && s.symbol !== symbol)
    )
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendUnsubscribe(channel, symbol)
    }
  }

  private sendSubscribe(channel: string, symbol?: string): void {
    const msg: Record<string, unknown> = { action: 'subscribe', channel }
    if (symbol) msg.symbol = symbol
    this.ws?.send(JSON.stringify(msg))
  }

  private sendUnsubscribe(channel: string, symbol?: string): void {
    const msg: Record<string, unknown> = { action: 'unsubscribe', channel }
    if (symbol) msg.symbol = symbol
    this.ws?.send(JSON.stringify(msg))
  }

  private resubscribe(): void {
    this.subscriptionList.forEach((s) => this.sendSubscribe(s.channel, s.symbol))
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return
    this.closed = false
    this.closeWhenOpen = false
    const fullUrl = this.getConnectionUrl()
    try {
      this.ws = new WebSocket(fullUrl)
    } catch (e) {
      this.scheduleReconnect()
      return
    }
    this.ws.onopen = () => {
      if (this.closeWhenOpen) {
        this.ws?.close()
        return
      }
      this.reconnectAttempts = 0
      this.resubscribe()
    }
    this.ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data as string)
        if (raw.channel && raw.data !== undefined) {
          this.messageHandler?.({
            channel: raw.channel,
            symbol: raw.symbol,
            data: raw.data,
          })
        }
      } catch {
        // ignore non-JSON or malformed
      }
    }
    this.ws.onclose = () => {
      this.ws = null
      if (!this.closed) this.scheduleReconnect()
    }
    this.ws.onerror = () => {
      // close will follow
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer != null) return
    const delay = Math.min(
      DEFAULT_WS_RECONNECT_INITIAL_MS * 2 ** this.reconnectAttempts,
      DEFAULT_WS_RECONNECT_MAX_MS
    )
    this.reconnectAttempts += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  disconnect(): void {
    this.closed = true
    this.closeWhenOpen = true
    if (this.reconnectTimer != null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      if (this.ws.readyState === WebSocket.CONNECTING) {
        // Avoid "closed before connection is established"; close in onopen instead
        return
      }
      this.ws.close()
      this.ws = null
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsService = new WebSocketService()

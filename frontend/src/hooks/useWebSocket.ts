import { useEffect, useState, useRef, useCallback } from 'react'
import { wsManager } from '../api/websocket'

interface WebSocketMessage {
  channel: string
  data: Record<string, unknown>
}

/**
 * Hook for subscribing to a WebSocket channel.
 * Returns the latest message and connection status.
 * Automatically subscribes on mount and unsubscribes on unmount.
 *
 * Pass null as channel to disable the subscription.
 */
export function useWebSocket(channel: string | null) {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [isConnected, setIsConnected] = useState(wsManager.isConnected)

  // Throttle UI updates to ~5fps (200ms)
  const throttleRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingMsg = useRef<WebSocketMessage | null>(null)

  const handler = useCallback((msg: { channel: string; data: unknown }) => {
    const wsMsg = msg as WebSocketMessage
    pendingMsg.current = wsMsg
    if (!throttleRef.current) {
      throttleRef.current = setTimeout(() => {
        throttleRef.current = null
        if (pendingMsg.current) {
          setLastMessage(pendingMsg.current)
          pendingMsg.current = null
        }
      }, 200)
    }
  }, [])

  // Subscribe / unsubscribe on channel change
  useEffect(() => {
    if (!channel) return

    setLastMessage(null)
    wsManager.subscribe(channel, handler)

    return () => {
      wsManager.unsubscribe(channel, handler)
      if (throttleRef.current) {
        clearTimeout(throttleRef.current)
        throttleRef.current = null
      }
    }
  }, [channel, handler])

  // Track connection status
  useEffect(() => {
    const unsub = wsManager.onStatusChange(setIsConnected)
    return unsub
  }, [])

  return { lastMessage, isConnected }
}

import { useEffect } from 'react'
import { wsService } from '../api/websocket'

/**
 * Subscribe to a WebSocket channel on mount and unsubscribe on unmount.
 * Does not handle messages; the global handler (see App or WebSocketProvider) dispatches to Redux.
 */
export function useWebSocketSubscribe(channel: 'pool' | 'user' | 'orderbook', symbol?: string): void {
  useEffect(() => {
    wsService.subscribe(channel, symbol)
    return () => {
      wsService.unsubscribe(channel, symbol)
    }
  }, [channel, symbol])
}

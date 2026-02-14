/**
 * Centralized API endpoints and param builders.
 * All symbol-based GET endpoints use query params (symbol=...).
 */
import { toPoolApiPath } from '../utils/market'

export const API = {
  market: '/api/market',
  pool: '/api/pool',
  orderbook: '/api/orderbook',
} as const

/**
 * Build query params for pool endpoints.
 * Pool uses symbol format: {base}-{quote}-{settle}-{market}
 */
export function poolParams(
  symbol: string,
  extra?: Record<string, string | number>
): Record<string, string | number> {
  return { symbol: toPoolApiPath(symbol), ...extra }
}

/**
 * Build query params for orderbook endpoints.
 * Orderbook uses full symbol string (e.g. AMM/USDT-USDT:SPOT)
 */
export function orderbookParams(
  symbol: string,
  extra?: Record<string, string | number>
): Record<string, string | number> {
  return { symbol, ...extra }
}

/**
 * Build query params for market endpoints.
 */
export function marketParams(
  symbol: string,
  extra?: Record<string, string | number>
): Record<string, string | number> {
  return { symbol, ...extra }
}

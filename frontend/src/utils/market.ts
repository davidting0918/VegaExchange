import type { Symbol } from '../types'

/**
 * Convert symbol config to URL-safe market ID
 * Format: {base}-{quote}-{market}
 * Example: ETH-USDT-SPOT
 */
export function toMarketId(symbol: Symbol): string {
  const base = symbol.base?.toUpperCase() || ''
  const quote = symbol.quote?.toUpperCase() || ''
  const market = (symbol.market || 'spot').toUpperCase()
  return `${base}-${quote}-${market}`
}

/**
 * Parse market ID back to components
 */
export function parseMarketId(marketId: string): { base: string; quote: string; market: string } | null {
  const parts = marketId.split('-')
  if (parts.length < 2) return null
  
  return {
    base: parts[0].toUpperCase(),
    quote: parts[1].toUpperCase(),
    market: parts[2]?.toUpperCase() || 'SPOT',
  }
}

/**
 * Find symbol config by market ID
 */
export function findSymbolByMarketId(symbols: Symbol[], marketId: string): Symbol | undefined {
  const parsed = parseMarketId(marketId)
  if (!parsed) return undefined
  
  return symbols.find(s => 
    s.base?.toUpperCase() === parsed.base &&
    s.quote?.toUpperCase() === parsed.quote &&
    (s.market || 'spot').toUpperCase() === parsed.market
  )
}

/**
 * Get display name for a symbol
 * Example: "ETH/USDT"
 */
export function getDisplayName(symbol: Symbol): string {
  return `${symbol.base}/${symbol.quote}`
}

/**
 * Group symbols by engine type
 */
export function groupSymbolsByEngine(symbols: Symbol[]): {
  amm: Symbol[]
  clob: Symbol[]
} {
  return {
    amm: symbols.filter(s => s.engine_type === 0),
    clob: symbols.filter(s => s.engine_type === 1),
  }
}

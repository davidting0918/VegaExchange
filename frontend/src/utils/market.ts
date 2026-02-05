import type { Symbol } from '../types'

/**
 * Symbol path components for URL routing
 */
export interface SymbolPathComponents {
  base: string
  quote: string
  settle: string
  market: string
}

/**
 * Parse symbol string into path components
 * Symbol format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
 * Example: "AMM/USDT-USDT:SPOT" -> { base: "AMM", quote: "USDT", settle: "USDT", market: "SPOT" }
 */
export function parseSymbolToPath(symbolStr: string): SymbolPathComponents | null {
  // Format: BASE/QUOTE-SETTLE:MARKET
  const match = symbolStr.match(/^([^/]+)\/([^-]+)-([^:]+):(.+)$/)
  if (!match) return null
  
  return {
    base: match[1].toUpperCase(),
    quote: match[2].toUpperCase(),
    settle: match[3].toUpperCase(),
    market: match[4].toUpperCase(),
  }
}

/**
 * Build symbol string from path components
 */
export function buildSymbolFromPath(components: SymbolPathComponents): string {
  return `${components.base}/${components.quote}-${components.settle}:${components.market}`
}

/**
 * Build API path for pool endpoints
 * Returns: "{base}/{quote}/{settle}/{market}"
 */
export function toPoolApiPath(symbolStr: string): string {
  const parts = parseSymbolToPath(symbolStr)
  if (!parts) {
    // Fallback: just return the symbol as-is
    return symbolStr
  }
  return `${parts.base}/${parts.quote}/${parts.settle}/${parts.market}`
}

/**
 * Build frontend URL path for pool page
 * Returns: "/pools/{base}/{quote}/{settle}/{market}"
 */
export function toPoolUrlPath(symbol: Symbol | string): string {
  const symbolStr = typeof symbol === 'string' ? symbol : symbol.symbol
  const parts = parseSymbolToPath(symbolStr)
  if (!parts) {
    // Fallback for simple symbol format
    if (typeof symbol === 'object') {
      return `/pools/${symbol.base}/${symbol.quote}/${symbol.settle || symbol.quote}/${symbol.market || 'SPOT'}`
    }
    return `/pools/${symbolStr}`
  }
  return `/pools/${parts.base}/${parts.quote}/${parts.settle}/${parts.market}`
}

/**
 * Build frontend URL path for market page (CLOB)
 * Returns: "/market/{base}/{quote}/{settle}/{market}"
 */
export function toMarketUrlPath(symbol: Symbol | string): string {
  const symbolStr = typeof symbol === 'string' ? symbol : symbol.symbol
  const parts = parseSymbolToPath(symbolStr)
  if (!parts) {
    // Fallback for simple symbol format
    if (typeof symbol === 'object') {
      return `/market/${symbol.base}/${symbol.quote}/${symbol.settle || symbol.quote}/${symbol.market || 'SPOT'}`
    }
    return `/market/${symbolStr}`
  }
  return `/market/${parts.base}/${parts.quote}/${parts.settle}/${parts.market}`
}

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

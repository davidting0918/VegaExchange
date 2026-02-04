import BigNumber from 'bignumber.js'

// Configure BigNumber for crypto precision
BigNumber.config({
  DECIMAL_PLACES: 18,
  ROUNDING_MODE: BigNumber.ROUND_DOWN,
})

/**
 * Format a number with specified decimal places
 */
export function formatNumber(
  value: string | number | BigNumber,
  decimals: number = 2,
  trimZeros: boolean = true
): string {
  const bn = new BigNumber(value)
  if (bn.isNaN()) return '0'

  let formatted = bn.toFixed(decimals)
  if (trimZeros) {
    formatted = formatted.replace(/\.?0+$/, '')
  }
  return formatted
}

/**
 * Format currency with $ prefix
 */
export function formatUSD(value: string | number | BigNumber, decimals: number = 2): string {
  const bn = new BigNumber(value)
  if (bn.isNaN()) return '$0.00'

  const formatted = bn.toFixed(decimals)
  return `$${addThousandsSeparator(formatted)}`
}

/**
 * Format crypto amount with appropriate precision
 */
export function formatCrypto(
  value: string | number | BigNumber,
  symbol?: string,
  maxDecimals: number = 8
): string {
  const bn = new BigNumber(value)
  if (bn.isNaN()) return '0'

  // Determine appropriate decimal places based on value magnitude
  let decimals = maxDecimals
  if (bn.gte(1000)) decimals = 2
  else if (bn.gte(1)) decimals = 4
  else if (bn.gte(0.01)) decimals = 6

  const formatted = bn.toFixed(decimals).replace(/\.?0+$/, '')
  return symbol ? `${formatted} ${symbol}` : formatted
}

/**
 * Add thousands separator to a number string
 */
export function addThousandsSeparator(value: string): string {
  const parts = value.split('.')
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return parts.join('.')
}

/**
 * Format percentage
 */
export function formatPercentage(value: string | number | BigNumber, decimals: number = 2): string {
  const bn = new BigNumber(value)
  if (bn.isNaN()) return '0%'

  const formatted = bn.multipliedBy(100).toFixed(decimals)
  return `${formatted}%`
}

/**
 * Format price impact (show as negative percentage)
 */
export function formatPriceImpact(value: string | number | BigNumber): string {
  const bn = new BigNumber(value)
  if (bn.isNaN()) return '0%'

  const percentage = bn.multipliedBy(100)
  const formatted = percentage.toFixed(2)
  
  if (percentage.lte(0.01)) return '<0.01%'
  if (percentage.gte(1)) return `${formatted}%`
  return `${formatted}%`
}

/**
 * Shorten address/hash for display
 */
export function shortenAddress(address: string, chars: number = 4): string {
  if (!address) return ''
  if (address.length <= chars * 2 + 2) return address
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`
}

/**
 * Format timestamp to locale string
 */
export function formatTimestamp(timestamp: string | number | Date): string {
  const date = new Date(timestamp)
  return date.toLocaleString()
}

/**
 * Format relative time (e.g., "2 minutes ago")
 */
export function formatRelativeTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp)
  const now = new Date()
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`
  return date.toLocaleDateString()
}

/**
 * Parse and validate numeric input
 */
export function parseNumericInput(value: string): string {
  // Remove all non-numeric characters except decimal point
  let cleaned = value.replace(/[^\d.]/g, '')
  
  // Ensure only one decimal point
  const parts = cleaned.split('.')
  if (parts.length > 2) {
    cleaned = parts[0] + '.' + parts.slice(1).join('')
  }
  
  return cleaned
}

/**
 * Check if value is valid positive number
 */
export function isValidAmount(value: string): boolean {
  if (!value || value === '') return false
  const bn = new BigNumber(value)
  return !bn.isNaN() && bn.gt(0)
}

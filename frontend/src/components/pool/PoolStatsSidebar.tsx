import React from 'react'
import { formatCrypto, formatNumber } from '../../utils'
import type { PoolInfo } from '../../types'

interface PoolStatsSidebarProps {
  pool: PoolInfo | null
  tvl: number
}

export const PoolStatsSidebar: React.FC<PoolStatsSidebarProps> = ({ pool, tvl }) => {
  if (!pool) return null

  const reserveBase = parseFloat(pool.reserve_base)
  const reserveQuote = parseFloat(pool.reserve_quote)
  const price = parseFloat(pool.current_price)
  const baseValue = reserveBase * price
  const totalValue = baseValue + reserveQuote
  const basePercent = totalValue > 0 ? (baseValue / totalValue) * 100 : 50
  const quotePercent = totalValue > 0 ? (reserveQuote / totalValue) * 100 : 50

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-text-primary">Stats</h3>
      <div className="space-y-4">
        {/* Pool balances with ratio bar */}
        <div>
          <p className="text-xs text-text-tertiary mb-2">Pool balances</p>
          <div className="flex gap-2 text-sm text-text-primary mb-2">
            <span>{formatCrypto(pool.reserve_base)} {pool.base}</span>
            <span className="text-text-tertiary">/</span>
            <span>{formatCrypto(pool.reserve_quote)} {pool.quote}</span>
          </div>
          <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden flex">
            <div
              className="h-full bg-accent-blue rounded-l-full"
              style={{ width: `${basePercent}%` }}
            />
            <div
              className="h-full bg-accent-blue/60"
              style={{ width: `${quotePercent}%` }}
            />
          </div>
        </div>

        {/* TVL */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-secondary">TVL</span>
          <span className="text-sm font-medium text-text-primary">
            ${formatNumber(tvl, 2)}
          </span>
        </div>

        {/* 24H volume */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-secondary">24H volume</span>
          <span className="text-sm font-medium text-text-primary">
            {formatCrypto(pool.total_volume_quote)} {pool.quote}
          </span>
        </div>

        {/* 24H fees */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-secondary">24H fees</span>
          <span className="text-sm font-medium text-text-primary">
            ${formatNumber(parseFloat(pool.total_fees_collected), 2)}
          </span>
        </div>
      </div>
    </div>
  )
}

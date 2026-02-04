import React from 'react'
import { Card, CardHeader, LoadingSpinner } from '../common'
import { formatCrypto, formatNumber, formatPercentage } from '../../utils'
import type { PoolInfo as PoolInfoType } from '../../types'

interface PoolInfoProps {
  pool: PoolInfoType | null
  isLoading?: boolean
}

export const PoolInfo: React.FC<PoolInfoProps> = ({ pool, isLoading }) => {
  if (isLoading) {
    return (
      <Card className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </Card>
    )
  }

  if (!pool) {
    return (
      <Card>
        <div className="text-center py-8 text-text-secondary">
          Select a trading pair to view pool information
        </div>
      </Card>
    )
  }

  const { base, quote, reserve_base, reserve_quote, fee_rate, total_lp_shares, current_price, total_volume_base } = pool

  return (
    <Card>
      <CardHeader
        title="Pool Information"
        subtitle={`${base}/${quote} AMM Pool`}
      />

      <div className="space-y-4">
        {/* Current Price */}
        <div className="p-4 bg-bg-tertiary rounded-lg">
          <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">Current Price</p>
          <p className="text-2xl font-bold text-text-primary">
            {formatNumber(current_price, 6)} {quote}
          </p>
          <p className="text-sm text-text-secondary">per {base}</p>
        </div>

        {/* Pool Reserves */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-bg-tertiary rounded-lg">
            <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">{base} Reserve</p>
            <p className="text-lg font-semibold text-text-primary">
              {formatCrypto(reserve_base)}
            </p>
          </div>
          <div className="p-3 bg-bg-tertiary rounded-lg">
            <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">{quote} Reserve</p>
            <p className="text-lg font-semibold text-text-primary">
              {formatCrypto(reserve_quote)}
            </p>
          </div>
        </div>

        {/* Pool Stats */}
        <div className="space-y-3 pt-4 border-t border-border-default">
          <div className="flex justify-between items-center">
            <span className="text-sm text-text-secondary">Fee Rate</span>
            <span className="text-sm font-medium text-text-primary">
              {formatPercentage(fee_rate)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-text-secondary">Total LP Shares</span>
            <span className="text-sm font-medium text-text-primary">
              {formatNumber(total_lp_shares, 4)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-text-secondary">Total Volume ({base})</span>
            <span className="text-sm font-medium text-text-primary">
              {formatCrypto(total_volume_base)}
            </span>
          </div>
        </div>
      </div>
    </Card>
  )
}

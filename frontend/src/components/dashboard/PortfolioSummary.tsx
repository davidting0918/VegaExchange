import React from 'react'
import { Link } from 'react-router-dom'
import { Card, Button, LoadingSpinner } from '../common'
import { formatUSD } from '../../utils'

interface PortfolioSummaryProps {
  totalValueUsdt: string
  balanceCount: number
  isLoading?: boolean
}

export const PortfolioSummary: React.FC<PortfolioSummaryProps> = ({
  totalValueUsdt,
  balanceCount,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <Card className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </Card>
    )
  }

  return (
    <Card className="bg-gradient-to-br from-bg-secondary to-bg-tertiary">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
        {/* Portfolio Value */}
        <div>
          <p className="text-sm text-text-secondary mb-1">Total Portfolio Value</p>
          <h2 className="text-3xl font-bold text-text-primary">
            {formatUSD(totalValueUsdt)}
          </h2>
          <p className="text-sm text-text-tertiary mt-1">
            {balanceCount} {balanceCount === 1 ? 'asset' : 'assets'}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Link to="/trade">
            <Button variant="primary">
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
              Trade
            </Button>
          </Link>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-border-default">
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wide">24h Change</p>
          <p className="text-lg font-semibold text-accent-green">+0.00%</p>
        </div>
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wide">24h P&L</p>
          <p className="text-lg font-semibold text-text-primary">$0.00</p>
        </div>
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wide">Available</p>
          <p className="text-lg font-semibold text-text-primary">{formatUSD(totalValueUsdt)}</p>
        </div>
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wide">In Orders</p>
          <p className="text-lg font-semibold text-text-primary">$0.00</p>
        </div>
      </div>
    </Card>
  )
}

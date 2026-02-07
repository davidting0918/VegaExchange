import React from 'react'
import { Card, CardHeader, LoadingSpinner } from '../common'
import { formatCrypto, formatRelativeTime } from '../../utils'
import type { Trade } from '../../types'

interface TradeHistoryProps {
  trades: Trade[]
  isLoading?: boolean
  baseToken?: string
  quoteToken?: string
}

export const TradeHistory: React.FC<TradeHistoryProps> = ({
  trades,
  isLoading,
  baseToken = 'BASE',
  quoteToken = 'QUOTE',
}) => {
  // Show full loading only when we have no data (initial load)
  // When refreshing, keep previous data visible to avoid flash
  const showFullLoading = isLoading && trades.length === 0

  if (showFullLoading) {
    return (
      <Card className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader
        title="Transactions"
        subtitle="Latest pool activity"
        action={isLoading && trades.length > 0 ? <LoadingSpinner size="sm" /> : undefined}
      />

      {trades.length === 0 ? (
        <div className="text-center py-8 text-text-secondary">
          No recent transactions
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default">
                <th className="pb-3 font-medium">Time</th>
                <th className="pb-3 font-medium">Type</th>
                <th className="pb-3 font-medium">Price ({quoteToken})</th>
                <th className="pb-3 font-medium">{baseToken}</th>
                <th className="pb-3 font-medium text-right">{quoteToken}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {trades.slice(0, 10).map((trade) => {
                const isBuy = trade.side === 'buy' || trade.side === 0
                return (
                <tr key={trade.trade_id} className="text-sm">
                  <td className="py-3 text-text-tertiary">
                    {formatRelativeTime(trade.created_at)}
                  </td>
                  <td className={`py-3 font-medium ${isBuy ? 'text-accent-green' : 'text-accent-red'}`}>
                    {isBuy ? `Buy ${baseToken}` : `Sell ${baseToken}`}
                  </td>
                  <td className="py-3 text-text-primary">
                    {formatCrypto(trade.price)}
                  </td>
                  <td className="py-3 text-text-primary">
                    {formatCrypto(trade.quantity)}
                  </td>
                  <td className="py-3 text-text-primary text-right">
                    {formatCrypto(trade.quote_amount)}
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

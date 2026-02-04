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
  if (isLoading) {
    return (
      <Card className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader
        title="Recent Trades"
        subtitle="Latest market activity"
      />

      {trades.length === 0 ? (
        <div className="text-center py-8 text-text-secondary">
          No recent trades
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default">
                <th className="pb-3 font-medium">Price ({quoteToken})</th>
                <th className="pb-3 font-medium">Amount ({baseToken})</th>
                <th className="pb-3 font-medium text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {trades.slice(0, 10).map((trade) => (
                <tr key={trade.trade_id} className="text-sm">
                  <td className={`py-3 font-medium ${trade.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>
                    {formatCrypto(trade.price)}
                  </td>
                  <td className="py-3 text-text-primary">
                    {formatCrypto(trade.quantity)}
                  </td>
                  <td className="py-3 text-text-tertiary text-right">
                    {formatRelativeTime(trade.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

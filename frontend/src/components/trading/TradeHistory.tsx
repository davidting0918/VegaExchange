import React, { useMemo, useState, useEffect, useRef } from 'react'
import { Card, CardHeader, LoadingSpinner } from '../common'
import { formatCrypto, formatRelativeTime } from '../../utils'
import type { Trade } from '../../types'

interface TradeHistoryProps {
  trades: Trade[]
  isLoading?: boolean
  baseToken?: string
  quoteToken?: string
  /** When this changes (symbol/engine switch), page resets to 1. Data refresh does NOT reset. */
  symbolKey?: string
  /** Controlled page from URL; when provided, parent owns page state. */
  page?: number
  onPageChange?: (page: number) => void
}

export const TradeHistory: React.FC<TradeHistoryProps> = ({
  trades,
  isLoading,
  baseToken = 'BASE',
  quoteToken = 'QUOTE',
  symbolKey,
  page: controlledPage,
  onPageChange,
}) => {
  const pageSize = 15
  const [internalPage, setInternalPage] = useState(1)
  const isControlled = controlledPage != null && onPageChange != null
  const currentPage = isControlled ? controlledPage : internalPage
  const setCurrentPage = isControlled ? onPageChange : setInternalPage

  // Reset to first page only when symbol/engine changes, NOT when trades data refreshes.
  // Do NOT include onPageChange in deps: it can change identity when URL updates (e.g. after
  // clicking Next), which would re-run this effect and reset page to 1, breaking pagination.
  const onPageChangeRef = useRef(onPageChange)
  onPageChangeRef.current = onPageChange
  const prevSymbolKeyRef = useRef(symbolKey)
  useEffect(() => {
    if (prevSymbolKeyRef.current !== symbolKey) {
      prevSymbolKeyRef.current = symbolKey
      if (isControlled && onPageChangeRef.current) {
        onPageChangeRef.current(1)
      } else if (!isControlled) {
        setInternalPage(1)
      }
    }
  }, [symbolKey, isControlled])

  const { pageTrades, totalPages, displayedPage } = useMemo(() => {
    const totalTrades = trades.length
    const totalPages = Math.max(1, Math.ceil(totalTrades / pageSize))
    const safePage = Math.min(currentPage, totalPages)
    const offset = (safePage - 1) * pageSize
    const pageTrades = trades.slice(offset, offset + pageSize)
    return { pageTrades, totalPages, displayedPage: safePage }
  }, [trades, currentPage])

  // Sync URL when page from URL exceeds total pages (e.g. after refresh with fewer trades)
  useEffect(() => {
    if (isControlled && onPageChangeRef.current && totalPages >= 1 && currentPage > totalPages) {
      onPageChangeRef.current(totalPages)
    }
  }, [isControlled, totalPages, currentPage])

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
              {pageTrades.map((trade) => {
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
                )
              })}
            </tbody>
          </table>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border-default text-xs text-text-secondary">
              <div>
                Page {displayedPage} of {totalPages}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCurrentPage(Math.max(1, displayedPage - 1))}
                  disabled={displayedPage === 1}
                  aria-label="Previous page"
                  className={`p-2 rounded-md border text-xs ${
                    displayedPage === 1
                      ? 'border-border-muted text-text-tertiary cursor-not-allowed'
                      : 'border-border-default text-text-secondary hover:text-text-primary hover:border-text-secondary'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7 7" />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentPage(Math.min(totalPages, displayedPage + 1))}
                  disabled={displayedPage === totalPages}
                  aria-label="Next page"
                  className={`p-2 rounded-md border text-xs ${
                    displayedPage === totalPages
                      ? 'border-border-muted text-text-tertiary cursor-not-allowed'
                      : 'border-border-default text-text-secondary hover:text-text-primary hover:border-text-secondary'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

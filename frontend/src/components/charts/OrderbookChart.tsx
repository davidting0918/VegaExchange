import React, { useMemo } from 'react'
import type { OrderbookLevel } from '../../types'

interface OrderbookChartProps {
  bids: OrderbookLevel[]
  asks: OrderbookLevel[]
  maxLevels?: number
  onPriceClick?: (price: string) => void
}

export const OrderbookChart: React.FC<OrderbookChartProps> = ({
  bids,
  asks,
  maxLevels = 15,
  onPriceClick,
}) => {
  // Process orderbook data
  const { processedBids, processedAsks, maxQuantity, spread, spreadPercentage } = useMemo(() => {
    const limitedBids = bids.slice(0, maxLevels)
    const limitedAsks = asks.slice(0, maxLevels)

    // Calculate cumulative totals and find max quantity
    let bidTotal = 0
    let askTotal = 0
    
    const processedBids = limitedBids.map(level => {
      bidTotal += parseFloat(level.quantity)
      return { ...level, total: bidTotal }
    })

    const processedAsks = limitedAsks.map(level => {
      askTotal += parseFloat(level.quantity)
      return { ...level, total: askTotal }
    })

    const maxQuantity = Math.max(bidTotal, askTotal)

    // Calculate spread
    const bestBid = limitedBids[0] ? parseFloat(limitedBids[0].price) : 0
    const bestAsk = limitedAsks[0] ? parseFloat(limitedAsks[0].price) : 0
    const spread = bestAsk > 0 && bestBid > 0 ? bestAsk - bestBid : 0
    const spreadPercentage = bestBid > 0 ? (spread / bestBid) * 100 : 0

    return { processedBids, processedAsks: processedAsks.reverse(), maxQuantity, spread, spreadPercentage }
  }, [bids, asks, maxLevels])

  const formatPrice = (price: string): string => {
    const num = parseFloat(price)
    return num < 1 ? num.toFixed(6) : num.toFixed(2)
  }

  const formatQuantity = (quantity: string): string => {
    const num = parseFloat(quantity)
    if (num >= 1000) return `${(num / 1000).toFixed(2)}K`
    return num.toFixed(4)
  }

  const handlePriceClick = (price: string) => {
    if (onPriceClick) {
      onPriceClick(price)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="grid grid-cols-3 gap-2 px-3 py-2 text-xs text-text-tertiary border-b border-border-default">
        <span>Price</span>
        <span className="text-right">Size</span>
        <span className="text-right">Total</span>
      </div>

      {/* Asks (sells) - shown in reverse order (lowest ask at bottom) */}
      <div className="flex-1 overflow-y-auto">
        {processedAsks.map((level, index) => {
          const depthPercentage = maxQuantity > 0 ? (level.total / maxQuantity) * 100 : 0
          return (
            <div
              key={`ask-${index}`}
              className="relative grid grid-cols-3 gap-2 px-3 py-1 text-sm cursor-pointer hover:bg-bg-tertiary"
              onClick={() => handlePriceClick(level.price)}
            >
              {/* Depth bar background */}
              <div
                className="absolute right-0 top-0 bottom-0 bg-red-500/10"
                style={{ width: `${depthPercentage}%` }}
              />
              <span className="relative text-accent-red font-mono">
                {formatPrice(level.price)}
              </span>
              <span className="relative text-right text-text-secondary font-mono">
                {formatQuantity(level.quantity)}
              </span>
              <span className="relative text-right text-text-tertiary font-mono">
                {formatQuantity(String(level.total))}
              </span>
            </div>
          )
        })}
      </div>

      {/* Spread indicator */}
      <div className="px-3 py-2 bg-bg-tertiary border-y border-border-default">
        <div className="flex items-center justify-between text-sm">
          <span className="text-text-tertiary">Spread</span>
          <span className="text-text-primary font-mono">
            {formatPrice(String(spread))} ({spreadPercentage.toFixed(3)}%)
          </span>
        </div>
      </div>

      {/* Bids (buys) */}
      <div className="flex-1 overflow-y-auto">
        {processedBids.map((level, index) => {
          const depthPercentage = maxQuantity > 0 ? (level.total / maxQuantity) * 100 : 0
          return (
            <div
              key={`bid-${index}`}
              className="relative grid grid-cols-3 gap-2 px-3 py-1 text-sm cursor-pointer hover:bg-bg-tertiary"
              onClick={() => handlePriceClick(level.price)}
            >
              {/* Depth bar background */}
              <div
                className="absolute right-0 top-0 bottom-0 bg-green-500/10"
                style={{ width: `${depthPercentage}%` }}
              />
              <span className="relative text-accent-green font-mono">
                {formatPrice(level.price)}
              </span>
              <span className="relative text-right text-text-secondary font-mono">
                {formatQuantity(level.quantity)}
              </span>
              <span className="relative text-right text-text-tertiary font-mono">
                {formatQuantity(String(level.total))}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

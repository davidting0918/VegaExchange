import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTrading, useUser } from '../../hooks'
import { Card, CardHeader, Button, LoadingSpinner } from '../common'
import { TradeHistory } from '../trading/TradeHistory'
import { CandlestickChart, OrderbookChart } from '../charts'
import { marketService } from '../../api'
import { formatCrypto, formatNumber, parseNumericInput, isValidAmount, buildSymbolFromPath } from '../../utils'
import type { TradeSide, OrderType, OrderbookLevel, Order, Symbol as SymbolType } from '../../types'
import type { CandlestickData } from 'lightweight-charts'

export const MarketPage: React.FC = () => {
  const { base, quote, settle, market } = useParams<{
    base: string
    quote: string
    settle: string
    market: string
  }>()
  const navigate = useNavigate()
  
  // Build symbol from URL path components
  const decodedSymbol = useMemo(() => {
    if (!base || !quote || !settle || !market) return ''
    return buildSymbolFromPath({ base, quote, settle, market })
  }, [base, quote, settle, market])

  const {
    symbols,
    recentTrades,
    isLoading,
    loadSymbols,
  } = useTrading()

  const { balances } = useUser()

  // Local state
  const [symbolInfo, setSymbolInfo] = useState<SymbolType | null>(null)
  const [orderbook, setOrderbook] = useState<{ bids: OrderbookLevel[]; asks: OrderbookLevel[] }>({ bids: [], asks: [] })
  const [orderbookLoading, setOrderbookLoading] = useState(true)
  const [userOrders, _setUserOrders] = useState<Order[]>([])
  const [ordersLoading, _setOrdersLoading] = useState(false)

  // Order form state
  const [orderSide, setOrderSide] = useState<TradeSide>('buy')
  const [orderType, setOrderType] = useState<OrderType>('limit')
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState('')
  const [isPlacingOrder, setIsPlacingOrder] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Find symbol info
  useEffect(() => {
    if (symbols.length === 0) {
      loadSymbols()
    } else {
      const info = symbols.find(s => s.symbol === decodedSymbol)
      setSymbolInfo(info || null)
    }
  }, [symbols, decodedSymbol, loadSymbols])

  // Load orderbook
  const loadOrderbook = useCallback(async () => {
    if (!decodedSymbol) return
    try {
      const response = await marketService.getOrderbook(decodedSymbol, 20)
      if (response.success && response.data) {
        setOrderbook(response.data)
      }
    } catch (err) {
      console.error('Failed to load orderbook:', err)
    } finally {
      setOrderbookLoading(false)
    }
  }, [decodedSymbol])

  // Load recent trades for CLOB
  const loadTrades = useCallback(async () => {
    if (!decodedSymbol) return
    try {
      await marketService.getRecentTrades(decodedSymbol, 1, 50) // 1 = CLOB engine type
    } catch (err) {
      console.error('Failed to load trades:', err)
    }
  }, [decodedSymbol])

  // Initial data load
  useEffect(() => {
    if (decodedSymbol) {
      loadOrderbook()
      loadTrades()
    }
  }, [decodedSymbol, loadOrderbook, loadTrades])

  // Auto refresh orderbook every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) {
        loadOrderbook()
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [decodedSymbol, loadOrderbook])

  // Get user balances
  const baseBalance = useMemo(() => {
    if (!symbolInfo || !balances) return '0'
    const balance = balances.find(b => b.currency === symbolInfo.base)
    return balance?.available || '0'
  }, [symbolInfo, balances])

  const quoteBalance = useMemo(() => {
    if (!symbolInfo || !balances) return '0'
    const balance = balances.find(b => b.currency === symbolInfo.quote)
    return balance?.available || '0'
  }, [symbolInfo, balances])

  // Get best prices from orderbook
  const bestBid = useMemo(() => {
    return orderbook.bids[0]?.price || '0'
  }, [orderbook.bids])

  const bestAsk = useMemo(() => {
    return orderbook.asks[0]?.price || '0'
  }, [orderbook.asks])

  const midPrice = useMemo(() => {
    const bid = parseFloat(bestBid)
    const ask = parseFloat(bestAsk)
    if (bid > 0 && ask > 0) {
      return (bid + ask) / 2
    }
    return symbolInfo?.current_price || 0
  }, [bestBid, bestAsk, symbolInfo])

  // Generate mock candlestick data (in real app, this would come from API)
  const candlestickData: CandlestickData[] = useMemo(() => {
    if (!midPrice) return []
    const now = Math.floor(Date.now() / 1000)
    const data: CandlestickData[] = []
    
    let prevClose = midPrice * 0.95
    
    // Generate 48 hours of hourly candles
    for (let i = 48; i >= 0; i--) {
      const time = now - i * 3600
      const variation = (Math.random() - 0.5) * 0.02 * prevClose
      const open = prevClose
      const close = open + variation
      const high = Math.max(open, close) * (1 + Math.random() * 0.01)
      const low = Math.min(open, close) * (1 - Math.random() * 0.01)
      
      data.push({
        time: time as CandlestickData['time'],
        open,
        high,
        low,
        close,
      })
      prevClose = close
    }
    return data
  }, [midPrice])

  // Calculate order total
  const orderTotal = useMemo(() => {
    const p = parseFloat(price) || 0
    const q = parseFloat(quantity) || 0
    return p * q
  }, [price, quantity])

  // Handle price click from orderbook
  const handlePriceClick = (clickedPrice: string) => {
    setPrice(clickedPrice)
  }

  // Handle order submission
  const handlePlaceOrder = async () => {
    if (!decodedSymbol || !symbolInfo) return
    
    // Validation
    if (orderType === 'limit' && (!price || !isValidAmount(price))) {
      setError('Please enter a valid price')
      return
    }
    if (!quantity || !isValidAmount(quantity)) {
      setError('Please enter a valid quantity')
      return
    }

    setIsPlacingOrder(true)
    setError(null)
    setSuccessMessage(null)

    try {
      // TODO: Call backend API to place order
      // For now, show a mock success message
      // const response = await tradeService.placeOrder({
      //   symbol: decodedSymbol,
      //   side: orderSide,
      //   order_type: orderType,
      //   price: orderType === 'limit' ? price : undefined,
      //   quantity,
      // })
      
      // Mock success for demonstration
      await new Promise(resolve => setTimeout(resolve, 500))
      
      setSuccessMessage(`${orderSide.toUpperCase()} order placed successfully`)
      setPrice('')
      setQuantity('')
      
      // Refresh orderbook
      loadOrderbook()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place order')
    } finally {
      setIsPlacingOrder(false)
    }
  }

  // Handle order cancellation
  const handleCancelOrder = async (orderId: string) => {
    // TODO: Implement order cancellation
    console.log('Cancel order:', orderId)
  }

  // Handle back navigation
  const handleBack = () => {
    navigate('/trade')
  }

  // Set market order price
  const handleSetMarketPrice = () => {
    setPrice(orderSide === 'buy' ? bestAsk : bestBid)
  }

  if (isLoading && !symbolInfo) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!symbolInfo) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={handleBack}>
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </Button>
        </div>
        <Card className="text-center py-12">
          <p className="text-text-secondary">Market not found</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={handleBack}>
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {symbolInfo.base}/{symbolInfo.quote}
            </h1>
            <p className="text-text-secondary">Order Book Market</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-text-tertiary">Last Price</p>
          <p className="text-2xl font-bold text-text-primary">
            {formatNumber(midPrice, 6)} {symbolInfo.quote}
          </p>
          <div className="flex items-center justify-end gap-4 mt-1 text-sm">
            <span className="text-accent-green">Bid: {formatNumber(parseFloat(bestBid), 6)}</span>
            <span className="text-accent-red">Ask: {formatNumber(parseFloat(bestAsk), 6)}</span>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-3 space-y-6">
          {/* Price Chart */}
          <Card>
            <CardHeader
              title="Price Chart"
              subtitle="1 hour candles"
            />
            <div className="pt-4">
              <CandlestickChart data={candlestickData} height={350} />
            </div>
          </Card>

          {/* Order Form and Recent Trades Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Order Form */}
            <Card>
              <CardHeader title="Place Order" />
              
              {/* Buy/Sell Tabs */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setOrderSide('buy')}
                  className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                    orderSide === 'buy'
                      ? 'bg-accent-green text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Buy
                </button>
                <button
                  onClick={() => setOrderSide('sell')}
                  className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                    orderSide === 'sell'
                      ? 'bg-accent-red text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Sell
                </button>
              </div>

              {/* Order Type Tabs */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setOrderType('limit')}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    orderType === 'limit'
                      ? 'bg-accent-blue text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Limit
                </button>
                <button
                  onClick={() => setOrderType('market')}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    orderType === 'market'
                      ? 'bg-accent-blue text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Market
                </button>
              </div>

              {/* Balance Display */}
              <div className="flex justify-between text-sm text-text-secondary mb-4">
                <span>Available:</span>
                <span className="font-mono">
                  {orderSide === 'buy'
                    ? `${formatCrypto(quoteBalance)} ${symbolInfo.quote}`
                    : `${formatCrypto(baseBalance)} ${symbolInfo.base}`}
                </span>
              </div>

              {/* Price Input (for limit orders) */}
              {orderType === 'limit' && (
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-text-secondary">Price</label>
                    <button
                      onClick={handleSetMarketPrice}
                      className="text-xs text-accent-blue hover:underline"
                    >
                      Market
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      value={price}
                      onChange={(e) => setPrice(parseNumericInput(e.target.value))}
                      placeholder="0.00"
                      className="w-full px-4 py-3 bg-bg-tertiary border border-border-default rounded-lg text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue font-mono"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary">
                      {symbolInfo.quote}
                    </span>
                  </div>
                </div>
              )}

              {/* Quantity Input */}
              <div className="mb-4">
                <div className="flex justify-between items-center mb-1">
                  <label className="text-sm text-text-secondary">Quantity</label>
                  <button
                    onClick={() => {
                      if (orderSide === 'sell') {
                        setQuantity(baseBalance)
                      } else if (price && parseFloat(price) > 0) {
                        const maxQty = parseFloat(quoteBalance) / parseFloat(price)
                        setQuantity(String(maxQty.toFixed(8)))
                      }
                    }}
                    className="text-xs text-accent-blue hover:underline"
                  >
                    Max
                  </button>
                </div>
                <div className="relative">
                  <input
                    type="text"
                    value={quantity}
                    onChange={(e) => setQuantity(parseNumericInput(e.target.value))}
                    placeholder="0.00"
                    className="w-full px-4 py-3 bg-bg-tertiary border border-border-default rounded-lg text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue font-mono"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary">
                    {symbolInfo.base}
                  </span>
                </div>
              </div>

              {/* Order Total */}
              {orderType === 'limit' && price && quantity && (
                <div className="mb-4 p-3 bg-bg-tertiary rounded-lg">
                  <div className="flex justify-between text-sm">
                    <span className="text-text-secondary">Total</span>
                    <span className="font-mono text-text-primary">
                      {formatNumber(orderTotal, 6)} {symbolInfo.quote}
                    </span>
                  </div>
                </div>
              )}

              {/* Error/Success Messages */}
              {error && (
                <div className="mb-4 p-3 bg-accent-red/10 border border-accent-red/20 rounded-lg text-accent-red text-sm">
                  {error}
                </div>
              )}
              {successMessage && (
                <div className="mb-4 p-3 bg-accent-green/10 border border-accent-green/20 rounded-lg text-accent-green text-sm">
                  {successMessage}
                </div>
              )}

              {/* Submit Button */}
              <Button
                fullWidth
                size="lg"
                variant={orderSide === 'buy' ? 'success' : 'danger'}
                onClick={handlePlaceOrder}
                isLoading={isPlacingOrder}
                disabled={!quantity || (orderType === 'limit' && !price)}
              >
                {orderSide === 'buy' ? `Buy ${symbolInfo.base}` : `Sell ${symbolInfo.base}`}
              </Button>
            </Card>

            {/* Recent Trades */}
            <TradeHistory
              trades={recentTrades}
              isLoading={isLoading}
              baseToken={symbolInfo.base}
              quoteToken={symbolInfo.quote}
              symbolKey={decodedSymbol}
            />
          </div>

          {/* Open Orders */}
          <Card>
            <CardHeader
              title="Open Orders"
              subtitle="Your pending orders"
            />
            {ordersLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner />
              </div>
            ) : userOrders.length === 0 ? (
              <div className="text-center py-8 text-text-secondary">
                No open orders
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default">
                      <th className="pb-3 font-medium">Side</th>
                      <th className="pb-3 font-medium">Type</th>
                      <th className="pb-3 font-medium">Price</th>
                      <th className="pb-3 font-medium">Quantity</th>
                      <th className="pb-3 font-medium">Filled</th>
                      <th className="pb-3 font-medium text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-default">
                    {userOrders.map((order) => (
                      <tr key={order.order_id} className="text-sm">
                        <td className={`py-3 font-medium ${order.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>
                          {order.side.toUpperCase()}
                        </td>
                        <td className="py-3 text-text-secondary">
                          {order.order_type.toUpperCase()}
                        </td>
                        <td className="py-3 text-text-primary font-mono">
                          {formatCrypto(order.price)}
                        </td>
                        <td className="py-3 text-text-primary font-mono">
                          {formatCrypto(order.quantity)}
                        </td>
                        <td className="py-3 text-text-secondary font-mono">
                          {formatCrypto(order.filled_quantity)}
                        </td>
                        <td className="py-3 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleCancelOrder(order.order_id)}
                          >
                            Cancel
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* Orderbook Sidebar */}
        <div className="lg:col-span-1">
          <Card className="h-[700px]">
            <CardHeader
              title="Order Book"
              subtitle={`${symbolInfo.base}/${symbolInfo.quote}`}
            />
            {orderbookLoading ? (
              <div className="flex items-center justify-center h-full">
                <LoadingSpinner />
              </div>
            ) : (
              <OrderbookChart
                bids={orderbook.bids}
                asks={orderbook.asks}
                maxLevels={15}
                onPriceClick={handlePriceClick}
              />
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

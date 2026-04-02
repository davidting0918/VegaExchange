import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import BigNumber from 'bignumber.js'
import { useTrading, useUser } from '../../hooks'
import { Card, CardHeader, Button, LoadingSpinner } from '../common'
import { TradeHistory } from '../trading/TradeHistory'
import { CandlestickChart, OrderbookChart } from '../charts'
import { marketService, tradeService } from '../../api'
import { formatCrypto, formatNumber, parseNumericInput, isValidAmount, buildSymbolFromPath } from '../../utils'
import { useWebSocket } from '../../hooks/useWebSocket'
import type { TradeSide, OrderType, OrderbookLevel, Order, Symbol as SymbolType, CandlestickData as AppCandlestickData } from '../../types'
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

  const { balances, loadBalances } = useUser()

  // Local state
  const [symbolInfo, setSymbolInfo] = useState<SymbolType | null>(null)
  const [orderbook, setOrderbook] = useState<{ bids: OrderbookLevel[]; asks: OrderbookLevel[] }>({ bids: [], asks: [] })
  const [orderbookLoading, setOrderbookLoading] = useState(true)

  // User orders state
  const [openOrders, setOpenOrders] = useState<Order[]>([])
  const [orderHistory, setOrderHistory] = useState<Order[]>([])
  const [ordersLoading, setOrdersLoading] = useState(false)
  const [ordersTab, setOrdersTab] = useState<'open' | 'history'>('open')
  const [cancellingOrders, setCancellingOrders] = useState<Set<string>>(new Set())

  // Kline / chart state
  const [klineData, setKlineData] = useState<CandlestickData[]>([])
  const [klineInterval, setKlineInterval] = useState<string>('1h')
  const [klineLoading, setKlineLoading] = useState(true)

  // Order form state
  const [orderSide, setOrderSide] = useState<TradeSide>('buy')
  const [orderType, setOrderType] = useState<OrderType>('limit')
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState('')
  const [isPlacingOrder, setIsPlacingOrder] = useState(false)
  const [showMarketConfirm, setShowMarketConfirm] = useState(false)
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

  // Load kline data from API
  const loadKlines = useCallback(async () => {
    if (!decodedSymbol) return
    try {
      const response = await marketService.getKlines(decodedSymbol, klineInterval, 200)
      if (response.success && response.data) {
        const mapped: CandlestickData[] = response.data.map((k: AppCandlestickData) => ({
          time: k.time as CandlestickData['time'],
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
        }))
        setKlineData(mapped)
      }
    } catch (err) {
      console.error('Failed to load klines:', err)
    } finally {
      setKlineLoading(false)
    }
  }, [decodedSymbol, klineInterval])

  // Load user orders
  const loadUserOrders = useCallback(async () => {
    if (!decodedSymbol) return
    try {
      setOrdersLoading(true)
      const [openRes, historyRes] = await Promise.all([
        tradeService.getUserOrders(decodedSymbol, ['pending', 'partial']),
        tradeService.getUserOrders(decodedSymbol, ['filled', 'cancelled'], 50),
      ])
      if (openRes.success && openRes.data) setOpenOrders(openRes.data)
      if (historyRes.success && historyRes.data) setOrderHistory(historyRes.data)
    } catch (err) {
      console.error('Failed to load user orders:', err)
    } finally {
      setOrdersLoading(false)
    }
  }, [decodedSymbol])

  // Initial kline + orders load
  useEffect(() => {
    if (decodedSymbol) {
      setKlineLoading(true)
      loadKlines()
      loadUserOrders()
    }
  }, [decodedSymbol, loadKlines, loadUserOrders])

  // WebSocket integration
  const { lastMessage: orderbookWs, isConnected: wsConnected } = useWebSocket(
    decodedSymbol ? `orderbook:${decodedSymbol}` : null
  )
  const { lastMessage: tradesWs } = useWebSocket(
    decodedSymbol ? `trades:${decodedSymbol}` : null
  )

  // Update orderbook from WebSocket
  useEffect(() => {
    if (orderbookWs?.data) {
      const d = orderbookWs.data as { bids?: OrderbookLevel[]; asks?: OrderbookLevel[] }
      if (d.bids && d.asks) {
        setOrderbook({ bids: d.bids, asks: d.asks })
        setOrderbookLoading(false)
      }
    }
  }, [orderbookWs])

  // Reload trades on WebSocket trade event
  useEffect(() => {
    if (tradesWs) {
      loadTrades()
    }
  }, [tradesWs, loadTrades])

  // Polling fallback: orderbook every 2s, orders every 3s, klines every 30s
  useEffect(() => {
    if (wsConnected) return // Skip polling when WS is connected
    const interval = setInterval(() => {
      if (decodedSymbol) loadOrderbook()
    }, 2000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadOrderbook, wsConnected])

  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) loadUserOrders()
    }, 3000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadUserOrders])

  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) loadKlines()
    }, 30000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadKlines])

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

  // Balance validation
  const insufficientBalance = useMemo(() => {
    if (!quantity || !isValidAmount(quantity)) return false
    const qty = new BigNumber(quantity)
    if (orderSide === 'buy') {
      if (orderType === 'limit' && price && isValidAmount(price)) {
        const total = qty.times(new BigNumber(price))
        return total.gt(new BigNumber(quoteBalance))
      }
      // For market orders, we can't precisely check without a quote
      return false
    } else {
      return qty.gt(new BigNumber(baseBalance))
    }
  }, [orderSide, orderType, price, quantity, baseBalance, quoteBalance])

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
    if (insufficientBalance) {
      setError('Insufficient balance')
      return
    }

    // Market order confirmation
    if (orderType === 'market' && !showMarketConfirm) {
      setShowMarketConfirm(true)
      return
    }
    setShowMarketConfirm(false)

    setIsPlacingOrder(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await tradeService.placeOrder({
        symbol: decodedSymbol,
        side: orderSide,
        order_type: orderType,
        price: orderType === 'limit' ? price : undefined,
        quantity,
      })

      if (response.success) {
        const d = response.data
        const filledQty = d.filled_quantity ?? '0'
        const avgPrice = d.price ?? price
        setSuccessMessage(
          `${orderSide.toUpperCase()} order placed — filled ${filledQty} @ ${avgPrice}`
        )
        setPrice('')
        setQuantity('')
        // Refresh related data
        loadOrderbook()
        loadUserOrders()
        loadBalances()
      } else {
        setError((response as { message?: string }).message || 'Order placement failed')
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: { message?: string } } } }
      const msg = axiosErr?.response?.data?.error?.message
      setError(msg || (err instanceof Error ? err.message : 'Failed to place order'))
    } finally {
      setIsPlacingOrder(false)
    }
  }

  // Handle order cancellation
  const handleCancelOrder = async (orderId: string) => {
    if (!decodedSymbol) return
    setCancellingOrders(prev => new Set(prev).add(orderId))
    try {
      const response = await tradeService.cancelOrder(decodedSymbol, orderId)
      if (response.success) {
        loadUserOrders()
        loadBalances()
      }
    } catch (err) {
      console.error('Failed to cancel order:', err)
    } finally {
      setCancellingOrders(prev => {
        const next = new Set(prev)
        next.delete(orderId)
        return next
      })
    }
  }

  // Cancel all open orders
  const handleCancelAll = async () => {
    if (!decodedSymbol || openOrders.length === 0) return
    for (const order of openOrders) {
      await handleCancelOrder(order.order_id)
    }
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
          <div className="flex items-center justify-end gap-2 mb-1">
            <span
              className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-accent-green' : 'bg-text-tertiary'}`}
              title={wsConnected ? 'Live' : 'Polling'}
            />
            <span className="text-xs text-text-tertiary">{wsConnected ? 'Live' : 'Polling'}</span>
          </div>
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
            <div className="flex items-center justify-between px-6 pt-4 pb-2">
              <h3 className="text-lg font-semibold text-text-primary">Price Chart</h3>
              <div className="flex gap-1">
                {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setKlineInterval(tf)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      klineInterval === tf
                        ? 'bg-accent-blue text-white'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary'
                    }`}
                  >
                    {tf.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="pt-2">
              {klineLoading && klineData.length === 0 ? (
                <div className="flex items-center justify-center" style={{ height: 350 }}>
                  <LoadingSpinner />
                </div>
              ) : klineData.length === 0 ? (
                <div className="flex items-center justify-center text-text-secondary" style={{ height: 350 }}>
                  No trade data available
                </div>
              ) : (
                <CandlestickChart data={klineData} height={350} />
              )}
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
                  onClick={() => { setOrderSide('buy'); setShowMarketConfirm(false) }}
                  className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                    orderSide === 'buy'
                      ? 'bg-accent-green text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Buy
                </button>
                <button
                  onClick={() => { setOrderSide('sell'); setShowMarketConfirm(false) }}
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
                  onClick={() => { setOrderType('limit'); setShowMarketConfirm(false) }}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    orderType === 'limit'
                      ? 'bg-accent-blue text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  Limit
                </button>
                <button
                  onClick={() => { setOrderType('market'); setShowMarketConfirm(false) }}
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

              {/* Insufficient balance warning */}
              {insufficientBalance && (
                <div className="mb-4 p-3 bg-accent-red/10 border border-accent-red/20 rounded-lg text-accent-red text-sm">
                  Insufficient {orderSide === 'buy' ? symbolInfo.quote : symbolInfo.base} balance
                </div>
              )}

              {/* Market order confirmation */}
              {showMarketConfirm && (
                <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-yellow-400 text-sm">
                  <p className="font-medium mb-1">Market Order Warning</p>
                  <p className="text-xs">Market orders execute at the best available price, which may differ significantly from the last price. Click again to confirm.</p>
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
                disabled={insufficientBalance || !quantity || (orderType === 'limit' && !price)}
              >
                {showMarketConfirm
                  ? 'Confirm Market Order'
                  : orderSide === 'buy'
                    ? `Buy ${symbolInfo.base}`
                    : `Sell ${symbolInfo.base}`}
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

          {/* Orders Panel */}
          <Card>
            <div className="flex items-center justify-between px-6 pt-4 pb-2">
              <div className="flex gap-4">
                <button
                  onClick={() => setOrdersTab('open')}
                  className={`text-sm font-medium pb-2 border-b-2 transition-colors ${
                    ordersTab === 'open'
                      ? 'text-text-primary border-accent-blue'
                      : 'text-text-secondary border-transparent hover:text-text-primary'
                  }`}
                >
                  Open Orders ({openOrders.length})
                </button>
                <button
                  onClick={() => setOrdersTab('history')}
                  className={`text-sm font-medium pb-2 border-b-2 transition-colors ${
                    ordersTab === 'history'
                      ? 'text-text-primary border-accent-blue'
                      : 'text-text-secondary border-transparent hover:text-text-primary'
                  }`}
                >
                  Order History
                </button>
              </div>
              {ordersTab === 'open' && openOrders.length > 0 && (
                <Button size="sm" variant="ghost" onClick={handleCancelAll}>
                  Cancel All
                </Button>
              )}
            </div>

            {ordersLoading && openOrders.length === 0 && orderHistory.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner />
              </div>
            ) : ordersTab === 'open' ? (
              openOrders.length === 0 ? (
                <div className="text-center py-8 text-text-secondary">No open orders</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default">
                        <th className="pb-3 pl-6 font-medium">Time</th>
                        <th className="pb-3 font-medium">Side</th>
                        <th className="pb-3 font-medium">Type</th>
                        <th className="pb-3 font-medium">Price</th>
                        <th className="pb-3 font-medium">Quantity</th>
                        <th className="pb-3 font-medium">Filled</th>
                        <th className="pb-3 font-medium">Status</th>
                        <th className="pb-3 pr-6 font-medium text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default">
                      {openOrders.map((order) => (
                        <tr key={order.order_id} className="text-sm">
                          <td className="py-3 pl-6 text-text-secondary text-xs">
                            {new Date(order.created_at).toLocaleTimeString()}
                          </td>
                          <td className={`py-3 font-medium ${order.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>
                            {order.side.toUpperCase()}
                          </td>
                          <td className="py-3 text-text-secondary">{order.order_type.toUpperCase()}</td>
                          <td className="py-3 text-text-primary font-mono">{formatCrypto(order.price)}</td>
                          <td className="py-3 text-text-primary font-mono">{formatCrypto(order.quantity)}</td>
                          <td className="py-3 font-mono">
                            <div className="flex items-center gap-2">
                              <span className="text-text-secondary">{formatCrypto(order.filled_quantity)}</span>
                              <div className="w-16 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-accent-blue rounded-full"
                                  style={{
                                    width: `${new BigNumber(order.filled_quantity).div(new BigNumber(order.quantity)).times(100).toNumber()}%`,
                                  }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              order.status === 'partial' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-accent-blue/10 text-accent-blue'
                            }`}>
                              {order.status.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-3 pr-6 text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleCancelOrder(order.order_id)}
                              isLoading={cancellingOrders.has(order.order_id)}
                            >
                              Cancel
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : (
              orderHistory.length === 0 ? (
                <div className="text-center py-8 text-text-secondary">No order history</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default">
                        <th className="pb-3 pl-6 font-medium">Time</th>
                        <th className="pb-3 font-medium">Side</th>
                        <th className="pb-3 font-medium">Type</th>
                        <th className="pb-3 font-medium">Price</th>
                        <th className="pb-3 font-medium">Quantity</th>
                        <th className="pb-3 font-medium">Filled</th>
                        <th className="pb-3 pr-6 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default">
                      {orderHistory.map((order) => (
                        <tr key={order.order_id} className="text-sm">
                          <td className="py-3 pl-6 text-text-secondary text-xs">
                            {new Date(order.created_at).toLocaleTimeString()}
                          </td>
                          <td className={`py-3 font-medium ${order.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>
                            {order.side.toUpperCase()}
                          </td>
                          <td className="py-3 text-text-secondary">{order.order_type.toUpperCase()}</td>
                          <td className="py-3 text-text-primary font-mono">{formatCrypto(order.price)}</td>
                          <td className="py-3 text-text-primary font-mono">{formatCrypto(order.quantity)}</td>
                          <td className="py-3 text-text-secondary font-mono">{formatCrypto(order.filled_quantity)}</td>
                          <td className="py-3 pr-6">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              order.status === 'filled' ? 'bg-accent-green/10 text-accent-green' : 'bg-text-tertiary/10 text-text-tertiary'
                            }`}>
                              {order.status.toUpperCase()}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
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

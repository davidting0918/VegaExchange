import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import BigNumber from 'bignumber.js'
import { useTrading, useUser } from '../../hooks'
import { Button, LoadingSpinner } from '../common'
import { CandlestickChart, OrderbookChart } from '../charts'
import { MarketPairsSidebar } from './MarketPairsSidebar'
import { marketService, tradeService } from '../../api'
import { formatCrypto, formatNumber, parseNumericInput, isValidAmount, buildSymbolFromPath, parsePairParam } from '../../utils'
import { useWebSocket } from '../../hooks/useWebSocket'
import type { TradeSide, OrderType, OrderbookLevel, Order, Trade, Symbol as SymbolType, CandlestickData as AppCandlestickData, OrderStatus } from '../../types'
import type { CandlestickData } from 'lightweight-charts'

// Backend sends integer enum values over WebSocket
const WS_STATUS_MAP: Record<number, OrderStatus> = {
  0: 'pending',
  1: 'partial',
  2: 'filled',
  3: 'cancelled',
}

const WS_SIDE_MAP: Record<number, TradeSide> = {
  0: 'buy',
  1: 'sell',
}

export const MarketPage: React.FC = () => {
  const { pair } = useParams<{ pair: string }>()

  // Build symbol from simplified URL param (e.g. "BTC-USDT" → "BTC/USDT-USDT:SPOT")
  const decodedSymbol = useMemo(() => {
    if (!pair) return ''
    const components = parsePairParam(pair, 'SPOT')
    if (!components) return ''
    return buildSymbolFromPath(components)
  }, [pair])

  const {
    symbols,
    loadSymbols,
  } = useTrading()

  const { user, balances, loadBalances } = useUser()

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

  // Local trades state (owned locally instead of Redux to avoid polluting global state)
  const [localTrades, setLocalTrades] = useState<Trade[]>([])
  const [tradesLoading, setTradesLoading] = useState(true)

  // Toast notification state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'info' } | null>(null)

  // Kline / chart state
  const [klineData, setKlineData] = useState<CandlestickData[]>([])
  const [klineInterval, setKlineInterval] = useState<string>('1h')
  const [klineLoading, setKlineLoading] = useState(true)

  // Order form state
  const [orderSide, setOrderSide] = useState<TradeSide>('buy')
  const [orderType, setOrderType] = useState<OrderType>('limit')
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState('')
  const [, setIsPlacingOrder] = useState(false)
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

  // Load recent trades for CLOB into local state
  const loadTrades = useCallback(async () => {
    if (!decodedSymbol) return
    try {
      const response = await marketService.getRecentTrades(decodedSymbol, 1, 50)
      if (response.success && response.data) {
        const raw = response.data as Trade[] | { trades: Trade[] }
        const trades = Array.isArray(raw) ? raw : raw.trades
        setLocalTrades(trades)
      }
    } catch (err) {
      console.error('Failed to load trades:', err)
    } finally {
      setTradesLoading(false)
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
  // #21: Subscribe to private user channel for order/balance updates
  const { lastMessage: userWs } = useWebSocket(
    user?.user_id ? `user:${user.user_id}` : null
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

  // #23: Append trades incrementally from WebSocket payload
  useEffect(() => {
    if (!tradesWs?.data) return
    const d = tradesWs.data as {
      trade_id?: string
      price?: number
      quantity?: number
      side?: number
      created_at?: string
      symbol?: string
    }
    // Graceful fallback: if enriched fields missing, re-fetch full list
    if (!d.trade_id || !d.created_at) {
      loadTrades()
      return
    }
    // Only prepend if matching current symbol
    if (d.symbol && d.symbol !== decodedSymbol) return

    const newTrade: Trade = {
      trade_id: d.trade_id,
      symbol: d.symbol || decodedSymbol,
      side: d.side !== undefined ? (WS_SIDE_MAP[d.side] || 'buy') : 'buy',
      engine_type: 1, // CLOB
      price: String(d.price ?? 0),
      quantity: String(d.quantity ?? 0),
      quote_amount: String((d.price ?? 0) * (d.quantity ?? 0)),
      fee_amount: '0',
      fee_asset: symbolInfo?.quote || 'USDT',
      status: 1,
      created_at: d.created_at,
    }
    setLocalTrades(prev => [newTrade, ...prev].slice(0, 50))
  }, [tradesWs, decodedSymbol, loadTrades, symbolInfo])

  // #21: Handle private user events (order_update)
  useEffect(() => {
    if (!userWs?.data) return
    const d = userWs.data as {
      type?: string
      order_id?: string
      symbol?: string
      side?: number
      status?: number
      filled_quantity?: number
      remaining_quantity?: number
      fill_price?: number
      fee_amount?: number
      fee_asset?: string
      is_taker?: boolean
    }
    if (d.type !== 'order_update') return
    // Only process events for the current symbol
    if (d.symbol && d.symbol !== decodedSymbol) return

    const mappedStatus = d.status !== undefined ? WS_STATUS_MAP[d.status] : undefined
    if (!mappedStatus || !d.order_id) return

    if (mappedStatus === 'filled' || mappedStatus === 'cancelled') {
      // Move order from open to history
      setOpenOrders(prev => {
        const order = prev.find(o => o.order_id === d.order_id)
        if (order) {
          const updated: Order = {
            ...order,
            status: mappedStatus,
            filled_quantity: String(d.filled_quantity ?? order.filled_quantity),
            remaining_quantity: '0',
          }
          setOrderHistory(hist => [updated, ...hist])
        }
        return prev.filter(o => o.order_id !== d.order_id)
      })

      // Show toast notification
      if (mappedStatus === 'filled') {
        const sideLabel = d.side !== undefined ? WS_SIDE_MAP[d.side]?.toUpperCase() : ''
        setToast({
          message: `${sideLabel} order filled @ ${d.fill_price ?? ''}`,
          type: 'success',
        })
      }

      // Refresh balances immediately
      loadBalances()
    } else if (mappedStatus === 'partial') {
      // Update fill progress in open orders
      setOpenOrders(prev =>
        prev.map(o =>
          o.order_id === d.order_id
            ? {
                ...o,
                status: 'partial' as OrderStatus,
                filled_quantity: String(d.filled_quantity ?? o.filled_quantity),
                remaining_quantity: String(d.remaining_quantity ?? o.remaining_quantity),
              }
            : o
        )
      )
      loadBalances()
    }
  }, [userWs, decodedSymbol, loadBalances])

  // Polling fallback: orderbook every 2s (only if WS disconnected)
  useEffect(() => {
    if (wsConnected) return
    const interval = setInterval(() => {
      if (decodedSymbol) loadOrderbook()
    }, 2000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadOrderbook, wsConnected])

  // #22: User orders polling — only as fallback when WS disconnected (10s instead of 3s)
  useEffect(() => {
    if (wsConnected) return // WS handles order updates via user channel
    const interval = setInterval(() => {
      if (decodedSymbol) loadUserOrders()
    }, 10000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadUserOrders, wsConnected])

  // Klines polling every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) loadKlines()
    }, 30000)
    return () => clearInterval(interval)
  }, [decodedSymbol, loadKlines])

  // Auto-dismiss toast after 3 seconds
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(timer)
  }, [toast])

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

  if (symbols.length === 0 && !symbolInfo) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!symbolInfo) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-text-secondary">Market not found</p>
      </div>
    )
  }

  // Shared order form renderer (used for both buy and sell sides)
  const renderOrderForm = (side: TradeSide) => {
    const isBuy = side === 'buy'
    const availBalance = isBuy ? quoteBalance : baseBalance
    const availAsset = isBuy ? symbolInfo.quote : symbolInfo.base

    const setQtyPercent = (pct: number) => {
      if (isBuy) {
        if (price && parseFloat(price) > 0) {
          const maxQty = (parseFloat(availBalance) * pct) / 100 / parseFloat(price)
          setQuantity(maxQty.toFixed(8))
        }
      } else {
        const qty = (parseFloat(availBalance) * pct) / 100
        setQuantity(qty.toFixed(8))
      }
      setOrderSide(side)
    }

    return (
      <div className="flex-1 p-3">
        {/* Available balance */}
        <div className="flex justify-between text-xs text-text-tertiary mb-2">
          <span>Avail</span>
          <span className="font-mono">{formatCrypto(availBalance)} {availAsset}</span>
        </div>

        {/* Price Input (limit only) */}
        {orderType === 'limit' && (
          <div className="mb-2">
            <div className="relative">
              <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-text-tertiary">Price</span>
              <input
                type="text"
                value={price}
                onChange={(e) => { setPrice(parseNumericInput(e.target.value)); setOrderSide(side) }}
                placeholder="0.00"
                className="w-full pl-12 pr-14 py-2 bg-bg-tertiary border border-border-default rounded text-xs text-text-primary font-mono focus:outline-none focus:border-accent-blue"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-text-tertiary">{symbolInfo.quote}</span>
            </div>
          </div>
        )}

        {/* Quantity Input */}
        <div className="mb-2">
          <div className="relative">
            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-text-tertiary">Qty</span>
            <input
              type="text"
              value={side === orderSide ? quantity : ''}
              onChange={(e) => { setQuantity(parseNumericInput(e.target.value)); setOrderSide(side) }}
              placeholder="0.00"
              className="w-full pl-10 pr-14 py-2 bg-bg-tertiary border border-border-default rounded text-xs text-text-primary font-mono focus:outline-none focus:border-accent-blue"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-text-tertiary">{symbolInfo.base}</span>
          </div>
        </div>

        {/* Percentage buttons */}
        <div className="flex gap-1 mb-2">
          {[25, 50, 75, 100].map(pct => (
            <button
              key={pct}
              onClick={() => setQtyPercent(pct)}
              className="flex-1 py-1 text-xs text-text-tertiary bg-bg-tertiary rounded hover:text-text-secondary hover:bg-bg-hover"
            >
              {pct === 100 ? 'Max' : `${pct}%`}
            </button>
          ))}
        </div>

        {/* Total */}
        {orderType === 'limit' && price && (side === orderSide) && quantity && (
          <div className="flex justify-between text-xs text-text-tertiary mb-2">
            <span>Total</span>
            <span className="font-mono">{formatNumber(orderTotal, 6)} {symbolInfo.quote}</span>
          </div>
        )}

        {/* Submit */}
        <button
          onClick={() => { setOrderSide(side); setTimeout(handlePlaceOrder, 0) }}
          disabled={insufficientBalance || !quantity || (orderType === 'limit' && !price)}
          className={`w-full py-2 rounded text-xs font-medium text-white disabled:opacity-40 ${
            isBuy ? 'bg-accent-green hover:bg-accent-green/80' : 'bg-accent-red hover:bg-accent-red/80'
          }`}
        >
          {isBuy ? `Buy ${symbolInfo.base}` : `Sell ${symbolInfo.base}`}
        </button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in -m-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-fade-in ${
          toast.type === 'success' ? 'bg-accent-green/90 text-white' : 'bg-accent-blue/90 text-white'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Symbol Bar */}
      <div className="flex items-center gap-6 px-4 py-2 border-b border-border-default bg-bg-secondary">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">{symbolInfo.base}/{symbolInfo.quote}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-accent-green' : 'bg-text-tertiary'}`} />
        </div>
        <span className="text-sm font-mono text-text-primary">{formatNumber(midPrice, 6)}</span>
        <div className="flex items-center gap-4 text-xs text-text-tertiary">
          <span>Bid: <span className="text-accent-green font-mono">{formatNumber(parseFloat(bestBid), 6)}</span></span>
          <span>Ask: <span className="text-accent-red font-mono">{formatNumber(parseFloat(bestAsk), 6)}</span></span>
        </div>
      </div>

      {/* Error/Success messages */}
      {(error || successMessage || showMarketConfirm) && (
        <div className="px-4 py-1 border-b border-border-default">
          {error && <div className="py-1 text-xs text-accent-red">{error}</div>}
          {successMessage && <div className="py-1 text-xs text-accent-green">{successMessage}</div>}
          {showMarketConfirm && <div className="py-1 text-xs text-yellow-400">Market order: click Buy/Sell again to confirm</div>}
        </div>
      )}

      {/* 3-Column Layout */}
      <div className="flex" style={{ height: 'calc(100vh - 160px)' }}>
        {/* LEFT: Order Book */}
        <div className="w-[260px] flex-shrink-0 border-r border-border-default overflow-hidden flex flex-col">
          <div className="px-3 py-1.5 text-xs text-text-tertiary font-medium border-b border-border-default">
            Order Book
          </div>
          <div className="flex-1 overflow-hidden">
            {orderbookLoading ? (
              <div className="flex items-center justify-center h-full"><LoadingSpinner /></div>
            ) : (
              <OrderbookChart
                bids={orderbook.bids}
                asks={orderbook.asks}
                maxLevels={15}
                onPriceClick={handlePriceClick}
              />
            )}
          </div>
        </div>

        {/* CENTER: Chart + Order Form */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Interval selector */}
          <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border-default">
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
              <button
                key={tf}
                onClick={() => setKlineInterval(tf)}
                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                  klineInterval === tf
                    ? 'text-text-primary font-medium'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Chart */}
          <div className="flex-1 min-h-0">
            {klineLoading && klineData.length === 0 ? (
              <div className="flex items-center justify-center h-full"><LoadingSpinner /></div>
            ) : klineData.length === 0 ? (
              <div className="flex items-center justify-center h-full text-text-tertiary text-sm">No trade data</div>
            ) : (
              <CandlestickChart data={klineData} height={400} />
            )}
          </div>

          {/* Order Form — side by side Buy/Sell */}
          <div className="border-t border-border-default">
            {/* Order type tabs */}
            <div className="flex gap-3 px-3 py-1.5 border-b border-border-default">
              {(['limit', 'market'] as OrderType[]).map(t => (
                <button
                  key={t}
                  onClick={() => { setOrderType(t); setShowMarketConfirm(false) }}
                  className={`text-xs pb-1 border-b ${
                    orderType === t
                      ? 'text-text-primary border-text-primary font-medium'
                      : 'text-text-tertiary border-transparent hover:text-text-secondary'
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {/* Buy + Sell side by side */}
            <div className="flex divide-x divide-border-default">
              {renderOrderForm('buy')}
              {renderOrderForm('sell')}
            </div>
          </div>
        </div>

        {/* RIGHT: Market Pairs + Recent Trades */}
        <div className="w-[280px] flex-shrink-0 border-l border-border-default overflow-hidden">
          <MarketPairsSidebar
            currentSymbol={decodedSymbol}
            trades={localTrades}
            tradesLoading={tradesLoading}
          />
        </div>
      </div>

      {/* Bottom: Orders Panel */}
      <div className="border-t border-border-default">
        <div className="flex items-center justify-between px-4 py-1.5 border-b border-border-default">
          <div className="flex gap-4">
            <button
              onClick={() => setOrdersTab('open')}
              className={`text-xs pb-1 border-b ${
                ordersTab === 'open'
                  ? 'text-text-primary border-accent-blue font-medium'
                  : 'text-text-tertiary border-transparent hover:text-text-secondary'
              }`}
            >
              Open Orders ({openOrders.length})
            </button>
            <button
              onClick={() => setOrdersTab('history')}
              className={`text-xs pb-1 border-b ${
                ordersTab === 'history'
                  ? 'text-text-primary border-accent-blue font-medium'
                  : 'text-text-tertiary border-transparent hover:text-text-secondary'
              }`}
            >
              Order History
            </button>
          </div>
          {ordersTab === 'open' && openOrders.length > 0 && (
            <button onClick={handleCancelAll} className="text-xs text-text-tertiary hover:text-text-primary">
              Cancel All
            </button>
          )}
        </div>

        <div className="max-h-[200px] overflow-y-auto">
          {ordersLoading && openOrders.length === 0 && orderHistory.length === 0 ? (
            <div className="flex items-center justify-center py-6"><LoadingSpinner /></div>
          ) : ordersTab === 'open' ? (
            openOrders.length === 0 ? (
              <div className="text-center py-6 text-text-tertiary text-xs">No open orders</div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-text-tertiary border-b border-border-default">
                    <th className="py-1.5 pl-4 font-medium">Time</th>
                    <th className="py-1.5 font-medium">Side</th>
                    <th className="py-1.5 font-medium">Type</th>
                    <th className="py-1.5 font-medium">Price</th>
                    <th className="py-1.5 font-medium">Qty</th>
                    <th className="py-1.5 font-medium">Filled</th>
                    <th className="py-1.5 font-medium">Status</th>
                    <th className="py-1.5 pr-4 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {openOrders.map((order) => (
                    <tr key={order.order_id} className="text-xs">
                      <td className="py-1.5 pl-4 text-text-tertiary">{new Date(order.created_at).toLocaleTimeString()}</td>
                      <td className={`py-1.5 font-medium ${order.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>{order.side.toUpperCase()}</td>
                      <td className="py-1.5 text-text-secondary">{order.order_type.toUpperCase()}</td>
                      <td className="py-1.5 text-text-primary font-mono">{formatCrypto(order.price)}</td>
                      <td className="py-1.5 text-text-primary font-mono">{formatCrypto(order.quantity)}</td>
                      <td className="py-1.5 font-mono">
                        <div className="flex items-center gap-1">
                          <span className="text-text-secondary">{formatCrypto(order.filled_quantity)}</span>
                          <div className="w-10 h-1 bg-bg-tertiary rounded-full overflow-hidden">
                            <div className="h-full bg-accent-blue rounded-full" style={{ width: `${new BigNumber(order.filled_quantity).div(new BigNumber(order.quantity)).times(100).toNumber()}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="py-1.5">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${order.status === 'partial' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-accent-blue/10 text-accent-blue'}`}>{order.status.toUpperCase()}</span>
                      </td>
                      <td className="py-1.5 pr-4 text-right">
                        <Button size="sm" variant="ghost" onClick={() => handleCancelOrder(order.order_id)} isLoading={cancellingOrders.has(order.order_id)}>Cancel</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          ) : (
            orderHistory.length === 0 ? (
              <div className="text-center py-6 text-text-tertiary text-xs">No order history</div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-text-tertiary border-b border-border-default">
                    <th className="py-1.5 pl-4 font-medium">Time</th>
                    <th className="py-1.5 font-medium">Side</th>
                    <th className="py-1.5 font-medium">Type</th>
                    <th className="py-1.5 font-medium">Price</th>
                    <th className="py-1.5 font-medium">Qty</th>
                    <th className="py-1.5 font-medium">Filled</th>
                    <th className="py-1.5 pr-4 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {orderHistory.map((order) => (
                    <tr key={order.order_id} className="text-xs">
                      <td className="py-1.5 pl-4 text-text-tertiary">{new Date(order.created_at).toLocaleTimeString()}</td>
                      <td className={`py-1.5 font-medium ${order.side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>{order.side.toUpperCase()}</td>
                      <td className="py-1.5 text-text-secondary">{order.order_type.toUpperCase()}</td>
                      <td className="py-1.5 text-text-primary font-mono">{formatCrypto(order.price)}</td>
                      <td className="py-1.5 text-text-primary font-mono">{formatCrypto(order.quantity)}</td>
                      <td className="py-1.5 text-text-secondary font-mono">{formatCrypto(order.filled_quantity)}</td>
                      <td className="py-1.5 pr-4">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${order.status === 'filled' ? 'bg-accent-green/10 text-accent-green' : 'bg-text-tertiary/10 text-text-tertiary'}`}>{order.status.toUpperCase()}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          )}
        </div>
      </div>
    </div>
  )
}

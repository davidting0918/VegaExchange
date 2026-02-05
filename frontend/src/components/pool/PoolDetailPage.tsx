import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTrading, useUser } from '../../hooks'
import { Card, CardHeader, Button, LoadingSpinner } from '../common'
import { SwapPanel } from '../trading/SwapPanel'
import { TradeHistory } from '../trading/TradeHistory'
import { PriceLineChart, VolumeBarChart, LPPieChart } from '../charts'
import { formatCrypto, formatNumber, formatPercentage, buildSymbolFromPath } from '../../utils'
import type { TradeSide, VolumeDataPoint } from '../../types'
import type { LineData } from 'lightweight-charts'

export const PoolDetailPage: React.FC = () => {
  const params = useParams<{
    base: string
    quote: string
    settle: string
    market: string
  }>()
  const navigate = useNavigate()
  
  // Build symbol from URL path components
  const decodedSymbol = useMemo(() => {
    if (!params.base || !params.quote || !params.settle || !params.market) return ''
    return buildSymbolFromPath({
      base: params.base,
      quote: params.quote,
      settle: params.settle,
      market: params.market,
    })
  }, [params.base, params.quote, params.settle, params.market])

  const {
    poolInfo,
    lpPosition,
    quote,
    recentTrades,
    isLoading,
    isQuoteLoading,
    selectSymbol,
    getQuote,
    executeSwap,
    refreshPoolData,
  } = useTrading()

  const { balances } = useUser()

  const [isSwapping, setIsSwapping] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load pool data on mount
  useEffect(() => {
    if (decodedSymbol) {
      selectSymbol(decodedSymbol, 0) // 0 = AMM engine type
    }
  }, [decodedSymbol, selectSymbol])

  // Auto refresh pool data every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) {
        refreshPoolData()
      }
    }, 10000)

    return () => clearInterval(interval)
  }, [decodedSymbol, refreshPoolData])

  // Get user balances for the pool tokens
  const baseBalance = useMemo(() => {
    if (!poolInfo || !balances) return '0'
    const balance = balances.find(b => b.currency === poolInfo.base)
    return balance?.available || '0'
  }, [poolInfo, balances])

  const quoteBalance = useMemo(() => {
    if (!poolInfo || !balances) return '0'
    const balance = balances.find(b => b.currency === poolInfo.quote)
    return balance?.available || '0'
  }, [poolInfo, balances])

  // Calculate TVL
  const tvl = useMemo(() => {
    if (!poolInfo) return 0
    const reserveBase = parseFloat(poolInfo.reserve_base)
    const reserveQuote = parseFloat(poolInfo.reserve_quote)
    const price = parseFloat(poolInfo.current_price)
    return reserveBase * price + reserveQuote
  }, [poolInfo])

  // Generate mock price history data (in real app, this would come from API)
  const priceChartData: LineData[] = useMemo(() => {
    if (!poolInfo) return []
    const currentPrice = parseFloat(poolInfo.current_price)
    const now = Math.floor(Date.now() / 1000)
    const data: LineData[] = []
    
    // Generate 24 hours of mock data
    for (let i = 24; i >= 0; i--) {
      const time = now - i * 3600
      // Add some random variation around current price
      const variation = (Math.random() - 0.5) * 0.1 * currentPrice
      data.push({
        time: time as LineData['time'],
        value: currentPrice + variation,
      })
    }
    return data
  }, [poolInfo])

  // Generate mock volume data (in real app, this would come from API)
  const volumeChartData: VolumeDataPoint[] = useMemo(() => {
    if (!poolInfo) return []
    const totalVolume = parseFloat(poolInfo.total_volume_base)
    
    // Generate last 7 days of mock data
    const data: VolumeDataPoint[] = []
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const today = new Date().getDay()
    
    for (let i = 6; i >= 0; i--) {
      const dayIndex = (today - i + 7) % 7
      // Random volume distribution
      const dayVolume = (totalVolume / 7) * (0.5 + Math.random())
      data.push({
        time: days[dayIndex],
        volume: dayVolume,
      })
    }
    return data
  }, [poolInfo])

  // LP share percentage
  const lpSharePercentage = useMemo(() => {
    if (!lpPosition) return 0
    return parseFloat(lpPosition.share_percentage) * 100
  }, [lpPosition])

  // Handle get quote
  const handleGetQuote = useCallback(async (amount: string, side: TradeSide) => {
    if (!decodedSymbol) return
    try {
      await getQuote({
        symbol: decodedSymbol,
        side,
        amount,
      })
    } catch (err) {
      console.error('Failed to get quote:', err)
    }
  }, [decodedSymbol, getQuote])

  // Handle swap
  const handleSwap = useCallback(async (amount: string, side: TradeSide, slippage: number) => {
    if (!decodedSymbol) return
    setIsSwapping(true)
    setError(null)
    try {
      await executeSwap({
        symbol: decodedSymbol,
        side,
        amount,
        slippage_tolerance: slippage,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Swap failed')
    } finally {
      setIsSwapping(false)
    }
  }, [decodedSymbol, executeSwap])

  // Handle back navigation
  const handleBack = () => {
    navigate('/trade')
  }

  if (isLoading && !poolInfo) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!poolInfo) {
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
          <p className="text-text-secondary">Pool not found</p>
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
              {poolInfo.base}/{poolInfo.quote} Pool
            </h1>
            <p className="text-text-secondary">AMM Liquidity Pool</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-text-tertiary">Current Price</p>
          <p className="text-2xl font-bold text-text-primary">
            {formatNumber(parseFloat(poolInfo.current_price), 6)} {poolInfo.quote}
          </p>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-accent-red/10 border border-accent-red/20 rounded-lg text-accent-red">
          {error}
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Stats and Charts */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pool Statistics */}
          <Card>
            <CardHeader title="Pool Statistics" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">TVL</p>
                <p className="text-lg font-semibold text-text-primary">
                  ${formatNumber(tvl, 2)}
                </p>
              </div>
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">24h Volume</p>
                <p className="text-lg font-semibold text-text-primary">
                  {formatCrypto(poolInfo.total_volume_base)} {poolInfo.base}
                </p>
              </div>
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">Fee Rate</p>
                <p className="text-lg font-semibold text-text-primary">
                  {formatPercentage(poolInfo.fee_rate)}
                </p>
              </div>
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">Total Fees</p>
                <p className="text-lg font-semibold text-text-primary">
                  ${formatNumber(parseFloat(poolInfo.total_fees_collected), 2)}
                </p>
              </div>
            </div>

            {/* Reserves */}
            <div className="mt-4 pt-4 border-t border-border-default">
              <p className="text-sm text-text-secondary mb-3">Pool Reserves</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-bg-tertiary rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">{poolInfo.base}</span>
                    <span className="font-mono text-text-primary">
                      {formatCrypto(poolInfo.reserve_base)}
                    </span>
                  </div>
                </div>
                <div className="p-3 bg-bg-tertiary rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">{poolInfo.quote}</span>
                    <span className="font-mono text-text-primary">
                      {formatCrypto(poolInfo.reserve_quote)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Price Chart */}
          <Card>
            <CardHeader
              title="Price Chart"
              subtitle="24 hour price history"
            />
            <div className="pt-4">
              <PriceLineChart data={priceChartData} height={250} />
            </div>
          </Card>

          {/* Volume Chart */}
          <Card>
            <CardHeader
              title="Volume"
              subtitle="7 day trading volume"
            />
            <div className="pt-4">
              <VolumeBarChart data={volumeChartData} height={180} />
            </div>
          </Card>

          {/* Recent Trades */}
          <TradeHistory
            trades={recentTrades}
            isLoading={isLoading}
            baseToken={poolInfo.base}
            quoteToken={poolInfo.quote}
          />
        </div>

        {/* Right Column - LP Position and Swap */}
        <div className="space-y-6">
          {/* LP Position */}
          <Card>
            <CardHeader
              title="Your LP Position"
              subtitle="Liquidity provider share"
            />
            {lpPosition ? (
              <div className="space-y-4">
                <LPPieChart userShare={lpSharePercentage} height={180} />
                
                <div className="space-y-3 pt-4 border-t border-border-default">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">LP Shares</span>
                    <span className="text-sm font-medium text-text-primary font-mono">
                      {formatNumber(parseFloat(lpPosition.lp_shares), 6)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">Share %</span>
                    <span className="text-sm font-medium text-text-primary">
                      {formatPercentage(lpPosition.share_percentage)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">{poolInfo.base} Amount</span>
                    <span className="text-sm font-medium text-text-primary font-mono">
                      {formatCrypto(lpPosition.base_amount)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">{poolInfo.quote} Amount</span>
                    <span className="text-sm font-medium text-text-primary font-mono">
                      {formatCrypto(lpPosition.quote_amount)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-text-secondary mb-2">No LP position</p>
                <p className="text-sm text-text-tertiary">
                  Add liquidity to earn fees from trades
                </p>
              </div>
            )}
          </Card>

          {/* Quick Swap Panel */}
          <SwapPanel
            pool={poolInfo}
            quote={quote}
            isQuoteLoading={isQuoteLoading}
            onGetQuote={handleGetQuote}
            onSwap={handleSwap}
            isSwapping={isSwapping}
            baseBalance={baseBalance}
            quoteBalance={quoteBalance}
          />
        </div>
      </div>
    </div>
  )
}

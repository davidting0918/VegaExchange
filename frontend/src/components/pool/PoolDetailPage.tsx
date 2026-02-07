import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useTrading, useUser } from '../../hooks'
import { Card, Button, LoadingSpinner, Modal } from '../common'
import { SwapPanel } from '../trading/SwapPanel'
import { TradeHistory } from '../trading/TradeHistory'
import { AddLiquidityPanel } from './AddLiquidityPanel'
import { PoolChartSection } from './PoolChartSection'
import { PoolStatsSidebar } from './PoolStatsSidebar'
import { LPPieChart } from '../charts'
import { formatCrypto, formatNumber, formatPercentage, buildSymbolFromPath, parsePoolUrlPath } from '../../utils'
import type { TradeSide } from '../../types'

export const PoolDetailPage: React.FC = () => {
  const { symbolPath } = useParams<{ symbolPath: string }>()
  const navigate = useNavigate()

  const decodedSymbol = useMemo(() => {
    const components = symbolPath ? parsePoolUrlPath(symbolPath) : null
    if (!components) return ''
    return buildSymbolFromPath(components)
  }, [symbolPath])

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
    addLiquidity,
    refreshPoolData,
  } = useTrading()

  const { balances } = useUser()

  const [isSwapping, setIsSwapping] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isAddLiquidityOpen, setIsAddLiquidityOpen] = useState(false)

  useEffect(() => {
    if (decodedSymbol) {
      selectSymbol(decodedSymbol, 0)
    }
  }, [decodedSymbol, selectSymbol])

  useEffect(() => {
    const interval = setInterval(() => {
      if (decodedSymbol) {
        refreshPoolData()
      }
    }, 10000)
    return () => clearInterval(interval)
  }, [decodedSymbol, refreshPoolData])

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

  const tvl = useMemo(() => {
    if (!poolInfo) return 0
    const reserveBase = parseFloat(poolInfo.reserve_base)
    const reserveQuote = parseFloat(poolInfo.reserve_quote)
    const price = parseFloat(poolInfo.current_price)
    return reserveBase * price + reserveQuote
  }, [poolInfo])

  const lpSharePercentage = useMemo(() => {
    if (!lpPosition) return 0
    return parseFloat(lpPosition.share_percentage) * 100
  }, [lpPosition])

  const handleGetQuote = useCallback(
    async (amount: string, side: TradeSide, amountType?: 'base' | 'quote') => {
      if (!decodedSymbol) return
      try {
        await getQuote({
          symbol: decodedSymbol,
          side,
          amount,
          amount_type: amountType ?? (side === 'buy' ? 'quote' : 'base'),
        })
      } catch (err) {
        console.error('Failed to get quote:', err)
      }
    },
    [decodedSymbol, getQuote]
  )

  const handleSwap = useCallback(
    async (amount: string, side: TradeSide) => {
      if (!decodedSymbol) return
      setIsSwapping(true)
      setError(null)
      try {
        await executeSwap({
          symbol: decodedSymbol,
          side,
          amount,
          // Do not send min_output so backend does not enforce slippage (accept any amount out)
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Swap failed')
      } finally {
        setIsSwapping(false)
      }
    },
    [decodedSymbol, executeSwap, quote]
  )

  const handleAddLiquidity = useCallback(
    async (baseAmount: string, quoteAmount: string) => {
      if (!decodedSymbol) return
      await addLiquidity({
        symbol: decodedSymbol,
        base_amount: baseAmount,
        quote_amount: quoteAmount,
      })
      setIsAddLiquidityOpen(false)
    },
    [decodedSymbol, addLiquidity]
  )

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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7 7 7-7" />
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

  const feePercent = (parseFloat(poolInfo.fee_rate) * 100).toFixed(2)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Uniswap-style compact header */}
      <div className="space-y-2">
        <nav className="text-sm">
          <Link to="/trade" className="text-text-tertiary hover:text-text-secondary">
            Pools
          </Link>
          <span className="text-text-tertiary mx-2">/</span>
          <span className="text-text-primary">
            {poolInfo.base}/{poolInfo.quote}
          </span>
          {poolInfo.pool_id && (
            <span className="text-text-tertiary ml-2 text-xs">
              {poolInfo.pool_id.length > 12
                ? `${poolInfo.pool_id.slice(0, 6)}...${poolInfo.pool_id.slice(-4)}`
                : poolInfo.pool_id}
            </span>
          )}
        </nav>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {poolInfo.base}/{poolInfo.quote} AMM {feePercent}%
            </h1>
            <p className="text-text-secondary text-sm mt-0.5">
              Current price: {formatNumber(parseFloat(poolInfo.current_price), 6)} {poolInfo.quote}
            </p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-text-primary">
              {formatCrypto(poolInfo.total_volume_quote)} {poolInfo.quote}
            </p>
            <p className="text-sm text-text-tertiary">Past day</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-accent-red/10 border border-accent-red/20 rounded-lg text-accent-red">
          {error}
        </div>
      )}

      {/* Main grid: left chart + transactions, right sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Chart + Transactions */}
        <div className="lg:col-span-2 space-y-6">
          <PoolChartSection pool={poolInfo} />
          <TradeHistory
            trades={recentTrades}
            isLoading={isLoading}
            baseToken={poolInfo.base}
            quoteToken={poolInfo.quote}
          />
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Action bar: Back + Add liquidity */}
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={handleBack}
              className="text-text-tertiary hover:text-text-primary text-sm flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Close
            </button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsAddLiquidityOpen(true)}
              className="flex items-center gap-2"
            >
              <span className="text-lg">+</span>
              Add liquidity
            </Button>
          </div>

          {/* Swap panel with tabs */}
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

          {/* Total APR placeholder */}
          <div className="p-4 bg-bg-tertiary rounded-lg">
            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Total APR</span>
              <span className="text-sm font-medium text-text-primary">—</span>
            </div>
          </div>

          {/* Stats */}
          <div className="p-4 bg-bg-secondary border border-border-default rounded-xl">
            <PoolStatsSidebar pool={poolInfo} tvl={tvl} />
          </div>

          {/* LP Position */}
          {(lpPosition && parseFloat(lpPosition.lp_shares) > 0) && (
            <div className="p-4 bg-bg-secondary border border-border-default rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-text-primary">Your Position</h3>
              <div className="min-h-[220px]">
                <LPPieChart userShare={lpSharePercentage} height={220} />
              </div>
              <div className="space-y-2 text-sm pt-2 border-t border-border-default">
                <div className="flex justify-between">
                  <span className="text-text-secondary">LP Shares</span>
                  <span className="font-medium text-text-primary font-mono">
                    {formatNumber(parseFloat(lpPosition.lp_shares), 6)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Share %</span>
                  <span className="font-medium text-text-primary">
                    {formatPercentage(lpPosition.share_percentage)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Links */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-text-primary">Links</h3>
            <div className="flex items-center gap-2 text-sm text-text-secondary">
              <span>{poolInfo.base}/{poolInfo.quote}</span>
              {poolInfo.pool_id && (
                <span className="font-mono text-xs text-text-tertiary">
                  {poolInfo.pool_id.length > 16
                    ? `${poolInfo.pool_id.slice(0, 8)}...${poolInfo.pool_id.slice(-8)}`
                    : poolInfo.pool_id}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Add Liquidity Modal */}
      <Modal
        isOpen={isAddLiquidityOpen}
        onClose={() => setIsAddLiquidityOpen(false)}
        title="Add Liquidity"
        size="xl"
      >
        <AddLiquidityPanel
          pool={poolInfo}
          symbol={decodedSymbol}
          onAddLiquidity={handleAddLiquidity}
          baseBalance={baseBalance}
          quoteBalance={quoteBalance}
          embedded
        />
      </Modal>
    </div>
  )
}

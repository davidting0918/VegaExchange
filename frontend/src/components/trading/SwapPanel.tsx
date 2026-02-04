import React, { useState, useEffect } from 'react'
import { Card, CardHeader, Button } from '../common'
import { formatCrypto, formatPriceImpact, parseNumericInput, isValidAmount } from '../../utils'
import type { PoolInfo, QuoteResponse, TradeSide } from '../../types'

interface SwapPanelProps {
  pool: PoolInfo | null
  quote: QuoteResponse | null
  isQuoteLoading: boolean
  onGetQuote: (amount: string, side: TradeSide) => Promise<void>
  onSwap: (amount: string, side: TradeSide, slippage: number) => Promise<void>
  isSwapping?: boolean
  baseBalance?: string
  quoteBalance?: string
}

export const SwapPanel: React.FC<SwapPanelProps> = ({
  pool,
  quote,
  isQuoteLoading,
  onGetQuote,
  onSwap,
  isSwapping = false,
  baseBalance = '0',
  quoteBalance = '0',
}) => {
  const [side, setSide] = useState<TradeSide>('buy')
  const [inputAmount, setInputAmount] = useState('')
  const [slippage, setSlippage] = useState(0.5) // 0.5%

  const fromToken = side === 'buy' ? pool?.quote : pool?.base
  const toToken = side === 'buy' ? pool?.base : pool?.quote
  const fromBalance = side === 'buy' ? quoteBalance : baseBalance
  const toBalance = side === 'buy' ? baseBalance : quoteBalance

  // Debounced quote fetch
  useEffect(() => {
    if (!inputAmount || !isValidAmount(inputAmount) || !pool) {
      return
    }

    const timer = setTimeout(() => {
      onGetQuote(inputAmount, side)
    }, 500)

    return () => clearTimeout(timer)
  }, [inputAmount, side, pool, onGetQuote])

  const handleInputChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setInputAmount(cleaned)
  }

  const handleSwapDirection = () => {
    setSide(side === 'buy' ? 'sell' : 'buy')
    setInputAmount('')
  }

  const handleMaxClick = () => {
    setInputAmount(fromBalance)
  }

  const handleSwap = async () => {
    if (!inputAmount || !isValidAmount(inputAmount)) return
    await onSwap(inputAmount, side, slippage / 100)
    setInputAmount('')
  }

  const slippageOptions = [0.1, 0.5, 1.0]

  return (
    <Card>
      <CardHeader
        title="Swap"
        subtitle="Exchange tokens instantly"
      />

      {!pool ? (
        <div className="text-center py-8 text-text-secondary">
          Select a trading pair to start swapping
        </div>
      ) : (
        <div className="space-y-4">
          {/* From Token */}
          <div className="p-4 bg-bg-tertiary rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-text-secondary">From</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary">
                  Balance: {formatCrypto(fromBalance)}
                </span>
                <button
                  type="button"
                  onClick={handleMaxClick}
                  className="text-xs text-accent-blue hover:underline"
                >
                  MAX
                </button>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="text"
                value={inputAmount}
                onChange={(e) => handleInputChange(e.target.value)}
                placeholder="0.00"
                className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
              />
              <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                <span className="font-medium text-text-primary">{fromToken}</span>
              </div>
            </div>
          </div>

          {/* Swap Direction Button */}
          <div className="flex justify-center -my-2 relative z-10">
            <button
              type="button"
              onClick={handleSwapDirection}
              className="w-10 h-10 bg-bg-secondary border border-border-default rounded-full flex items-center justify-center hover:border-accent-blue hover:text-accent-blue transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </button>
          </div>

          {/* To Token */}
          <div className="p-4 bg-bg-tertiary rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-text-secondary">To (estimated)</span>
              <span className="text-xs text-text-tertiary">
                Balance: {formatCrypto(toBalance)}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                {isQuoteLoading ? (
                  <div className="h-8 bg-bg-secondary rounded animate-pulse" />
                ) : (
                  <span className="text-2xl font-medium text-text-primary">
                    {quote ? formatCrypto(quote.output_amount) : '0.00'}
                  </span>
                )}
              </div>
              <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                <span className="font-medium text-text-primary">{toToken}</span>
              </div>
            </div>
          </div>

          {/* Quote Details */}
          {quote && (
            <div className="p-4 bg-bg-tertiary/50 rounded-lg space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Price</span>
                <span className="text-text-primary">
                  1 {fromToken} = {formatCrypto(quote.price)} {toToken}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Price Impact</span>
                <span className={parseFloat(quote.price_impact) > 0.01 ? 'text-accent-red' : 'text-text-primary'}>
                  {formatPriceImpact(quote.price_impact)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Fee</span>
                <span className="text-text-primary">
                  {formatCrypto(quote.fee_amount)} {quote.fee_asset}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Min Received</span>
                <span className="text-text-primary">
                  {quote.min_output ? formatCrypto(quote.min_output) : '-'} {toToken}
                </span>
              </div>
            </div>
          )}

          {/* Slippage Settings */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-text-secondary">Slippage Tolerance</span>
            </div>
            <div className="flex gap-2">
              {slippageOptions.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setSlippage(option)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    slippage === option
                      ? 'bg-accent-blue text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {option}%
                </button>
              ))}
              <input
                type="text"
                value={slippage}
                onChange={(e) => {
                  const val = parseFloat(e.target.value)
                  if (!isNaN(val) && val >= 0 && val <= 50) {
                    setSlippage(val)
                  }
                }}
                className="w-16 px-2 py-1.5 bg-bg-tertiary border border-border-default rounded-lg text-sm text-center text-text-primary focus:outline-none focus:border-accent-blue"
              />
            </div>
          </div>

          {/* Swap Button */}
          <Button
            fullWidth
            size="lg"
            variant={side === 'buy' ? 'success' : 'danger'}
            onClick={handleSwap}
            isLoading={isSwapping}
            disabled={!inputAmount || !isValidAmount(inputAmount) || !quote}
          >
            {side === 'buy' ? `Buy ${pool.base}` : `Sell ${pool.base}`}
          </Button>
        </div>
      )}
    </Card>
  )
}

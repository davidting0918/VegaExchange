import React, { useState, useEffect } from 'react'
import { Card, Button } from '../common'
import { formatCrypto, formatPriceImpact, parseNumericInput, isValidAmount } from '../../utils'
import type { PoolInfo, QuoteResponse, TradeSide } from '../../types'

type ActiveInput = 'base' | 'quote'

interface SwapPanelProps {
  pool: PoolInfo | null
  quote: QuoteResponse | null
  isQuoteLoading?: boolean
  onGetQuote: (amount: string, side: TradeSide, amountType?: 'base' | 'quote') => Promise<void>
  onSwap: (amount: string, side: TradeSide) => Promise<void>
  isSwapping?: boolean
  baseBalance?: string
  quoteBalance?: string
}

type SwapTab = 'swap' | 'limit' | 'buy' | 'sell'

export const SwapPanel: React.FC<SwapPanelProps> = ({
  pool,
  quote,
  onGetQuote,
  onSwap,
  isSwapping = false,
  baseBalance = '0',
  quoteBalance = '0',
}) => {
  const [activeTab, setActiveTab] = useState<SwapTab>('swap')
  const [baseAmount, setBaseAmount] = useState('')
  const [quoteAmount, setQuoteAmount] = useState('')
  const [activeInput, setActiveInput] = useState<ActiveInput>('base')
  /** When true, display quote token on top and base on bottom (e.g. USDT → AMM) */
  const [flipped, setFlipped] = useState(false)

  // Update the non-active field when quote response arrives
  useEffect(() => {
    if (!quote) return
    const output = quote.output_amount
    if (activeInput === 'base') {
      setQuoteAmount(output)
    } else {
      setBaseAmount(output)
    }
  }, [quote, activeInput])

  // Debounced quote fetch - only depends on active input value to avoid re-fetch when we update the other field from quote
  const activeAmount = activeInput === 'base' ? baseAmount : quoteAmount
  useEffect(() => {
    if (!pool) return

    if (!activeAmount || !isValidAmount(activeAmount)) {
      if (activeInput === 'base') {
        setQuoteAmount('')
      } else {
        setBaseAmount('')
      }
      return
    }

    const timer = setTimeout(() => {
      if (activeInput === 'base') {
        onGetQuote(activeAmount, 'sell', 'base')
      } else {
        onGetQuote(activeAmount, 'buy', 'quote')
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [activeAmount, activeInput, pool, onGetQuote])

  const handleBaseInputChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setActiveInput('base')
    setBaseAmount(cleaned)
  }

  const handleQuoteInputChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setActiveInput('quote')
    setQuoteAmount(cleaned)
  }

  const handleBaseMaxClick = () => {
    setActiveInput('base')
    setBaseAmount(baseBalance)
  }

  const handleQuoteMaxClick = () => {
    setActiveInput('quote')
    setQuoteAmount(quoteBalance)
  }

  const handleArrowClick = () => {
    setFlipped((prev) => !prev)
    setBaseAmount(quoteAmount)
    setQuoteAmount(baseAmount)
    setActiveInput((prev) => (prev === 'base' ? 'quote' : 'base'))
  }

  const handleSwap = async () => {
    if (activeInput === 'base') {
      if (!baseAmount || !isValidAmount(baseAmount)) return
      await onSwap(baseAmount, 'sell')
    } else {
      if (!quoteAmount || !isValidAmount(quoteAmount)) return
      await onSwap(quoteAmount, 'buy')
    }
    setBaseAmount('')
    setQuoteAmount('')
  }

  const hasValidInput = activeInput === 'base'
    ? baseAmount && isValidAmount(baseAmount)
    : quoteAmount && isValidAmount(quoteAmount)

  const fromToken = activeInput === 'base' ? pool?.base : pool?.quote
  const toToken = activeInput === 'base' ? pool?.quote : pool?.base

  const tabs: { id: SwapTab; label: string }[] = [
    { id: 'swap', label: 'Swap' },
    { id: 'limit', label: 'Limit' },
    { id: 'buy', label: 'Buy' },
    { id: 'sell', label: 'Sell' },
  ]

  return (
    <Card>
      <div className="flex border-b border-border-default">
        {tabs.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === id
                ? 'text-accent-blue border-accent-blue'
                : 'text-text-secondary border-transparent hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab !== 'swap' ? (
        <div className="py-12 text-center text-text-tertiary text-sm">
          Coming soon
        </div>
      ) : !pool ? (
        <div className="text-center py-8 text-text-secondary">
          Select a trading pair to start swapping
        </div>
      ) : (
        <div className="space-y-4">
          {/* Top Input - when flipped show quote (USDT), else show base (AMM) */}
          {flipped ? (
            <div className="p-4 bg-bg-tertiary rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-text-secondary">{pool.quote}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(quoteBalance)}
                  </span>
                  <button
                    type="button"
                    onClick={handleQuoteMaxClick}
                    className="text-xs text-accent-blue hover:underline"
                  >
                    MAX
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={quoteAmount}
                  onChange={(e) => handleQuoteInputChange(e.target.value)}
                  onFocus={() => setActiveInput('quote')}
                  placeholder="0.00"
                  className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                  <span className="font-medium text-text-primary">{pool.quote}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-bg-tertiary rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-text-secondary">{pool.base}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(baseBalance)}
                  </span>
                  <button
                    type="button"
                    onClick={handleBaseMaxClick}
                    className="text-xs text-accent-blue hover:underline"
                  >
                    MAX
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={baseAmount}
                  onChange={(e) => handleBaseInputChange(e.target.value)}
                  onFocus={() => setActiveInput('base')}
                  placeholder="0.00"
                  className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                  <span className="font-medium text-text-primary">{pool.base}</span>
                </div>
              </div>
            </div>
          )}

          {/* Swap Direction Indicator - click to swap top/bottom asset order */}
          <div className="flex justify-center -my-2 relative z-10">
            <button
              type="button"
              onClick={handleArrowClick}
              aria-label="Swap asset order"
              className="w-10 h-10 bg-bg-secondary border border-border-default rounded-full flex items-center justify-center text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary cursor-pointer transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
          </div>

          {/* Bottom Input - when flipped show base (AMM), else show quote (USDT) */}
          {flipped ? (
            <div className="p-4 bg-bg-tertiary rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-text-secondary">{pool.base}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(baseBalance)}
                  </span>
                  <button
                    type="button"
                    onClick={handleBaseMaxClick}
                    className="text-xs text-accent-blue hover:underline"
                  >
                    MAX
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={baseAmount}
                  onChange={(e) => handleBaseInputChange(e.target.value)}
                  onFocus={() => setActiveInput('base')}
                  placeholder="0.00"
                  className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                  <span className="font-medium text-text-primary">{pool.base}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-bg-tertiary rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-text-secondary">{pool.quote}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(quoteBalance)}
                  </span>
                  <button
                    type="button"
                    onClick={handleQuoteMaxClick}
                    className="text-xs text-accent-blue hover:underline"
                  >
                    MAX
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={quoteAmount}
                  onChange={(e) => handleQuoteInputChange(e.target.value)}
                  onFocus={() => setActiveInput('quote')}
                  placeholder="0.00"
                  className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                  <span className="font-medium text-text-primary">{pool.quote}</span>
                </div>
              </div>
            </div>
          )}

          {/* Quote Details */}
          {quote && hasValidInput && (
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
            </div>
          )}

          {/* Swap Button */}
          <Button
            fullWidth
            size="lg"
            variant="primary"
            onClick={handleSwap}
            isLoading={isSwapping}
            disabled={!hasValidInput || !quote}
          >
            Swap
          </Button>
        </div>
      )}
    </Card>
  )
}

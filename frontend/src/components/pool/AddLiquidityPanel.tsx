import React, { useState, useEffect } from 'react'
import { Card, CardHeader, Button } from '../common'
import { formatCrypto, parseNumericInput, isValidAmount } from '../../utils'
import { tradeService } from '../../api'
import type { PoolInfo } from '../../types'

interface AddLiquidityPanelProps {
  pool: PoolInfo | null
  symbol: string
  onAddLiquidity: (baseAmount: string, quoteAmount: string) => Promise<void>
  baseBalance?: string
  quoteBalance?: string
  /** When true, render without Card wrapper (e.g. for use in Modal) */
  embedded?: boolean
}

export const AddLiquidityPanel: React.FC<AddLiquidityPanelProps> = ({
  pool,
  symbol,
  onAddLiquidity,
  baseBalance = '0',
  quoteBalance = '0',
  embedded = false,
}) => {
  const [baseAmount, setBaseAmount] = useState('')
  const [quoteAmount, setQuoteAmount] = useState('')
  const [isQuoteLoading, setIsQuoteLoading] = useState(false)
  const [isAdding, setIsAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Debounced quote fetch when base amount changes
  useEffect(() => {
    if (!pool || !baseAmount || !isValidAmount(baseAmount)) {
      setQuoteAmount('')
      return
    }

    const timer = setTimeout(async () => {
      setIsQuoteLoading(true)
      setError(null)
      try {
        const response = await tradeService.getAddLiquidityQuote(symbol, baseAmount)
        if (response.success && response.data) {
          setQuoteAmount(response.data.quote_amount)
        } else {
          setQuoteAmount('')
          setError(response.message || 'Failed to get quote')
        }
      } catch (err) {
        setQuoteAmount('')
        setError(err instanceof Error ? err.message : 'Failed to get quote')
      } finally {
        setIsQuoteLoading(false)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [baseAmount, pool, symbol])

  const handleBaseInputChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setBaseAmount(cleaned)
  }

  const handleBaseMaxClick = () => {
    setBaseAmount(baseBalance)
  }

  const handleAddLiquidity = async () => {
    if (!baseAmount || !quoteAmount || !isValidAmount(baseAmount)) return
    const baseNum = parseFloat(baseAmount)
    const quoteNum = parseFloat(quoteAmount)
    if (baseNum > parseFloat(baseBalance)) {
      setError(`Insufficient ${pool?.base} balance`)
      return
    }
    if (quoteNum > parseFloat(quoteBalance)) {
      setError(`Insufficient ${pool?.quote} balance`)
      return
    }

    setIsAdding(true)
    setError(null)
    try {
      await onAddLiquidity(baseAmount, quoteAmount)
      setBaseAmount('')
      setQuoteAmount('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Add liquidity failed')
    } finally {
      setIsAdding(false)
    }
  }

  const hasValidInput = baseAmount && isValidAmount(baseAmount) && quoteAmount && isValidAmount(quoteAmount)
  const hasSufficientBalance =
    hasValidInput &&
    parseFloat(baseAmount) <= parseFloat(baseBalance) &&
    parseFloat(quoteAmount) <= parseFloat(quoteBalance)

  const content = (
    <>
      {!embedded && (
        <CardHeader
          title="Add Liquidity"
          subtitle="Deposit tokens to earn fees from trades"
        />
      )}
      {!pool ? (
        <div className="text-center py-8 text-text-secondary">
          Select a pool to add liquidity
        </div>
      ) : (
        <div className="space-y-4">
          {error && (
            <div className="p-3 bg-accent-red/10 border border-accent-red/20 rounded-lg text-accent-red text-sm">
              {error}
            </div>
          )}

          {/* Base Input (editable) */}
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
                placeholder="0.00"
                className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
              />
              <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                <span className="font-medium text-text-primary">{pool.base}</span>
              </div>
            </div>
          </div>

          {/* Plus indicator */}
          <div className="flex justify-center -my-2 relative z-10">
            <div className="w-10 h-10 bg-bg-secondary border border-border-default rounded-full flex items-center justify-center text-text-tertiary">
              <span className="text-xl font-medium">+</span>
            </div>
          </div>

          {/* Quote Input (read-only, computed from quote API) */}
          <div className="p-4 bg-bg-tertiary rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-text-secondary">{pool.quote}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary">
                  Balance: {formatCrypto(quoteBalance)}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="text"
                value={quoteAmount}
                readOnly
                placeholder={isQuoteLoading ? 'Calculating...' : '0.00'}
                className="flex-1 bg-transparent text-2xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none cursor-not-allowed"
              />
              <div className="px-3 py-1.5 bg-bg-secondary rounded-lg">
                <span className="font-medium text-text-primary">{pool.quote}</span>
              </div>
            </div>
          </div>

          <Button
            fullWidth
            size="lg"
            variant="primary"
            onClick={handleAddLiquidity}
            isLoading={isAdding}
            disabled={!hasValidInput || !hasSufficientBalance || isQuoteLoading}
          >
            Add Liquidity
          </Button>
        </div>
      )}
    </>
  )

  return embedded ? <div className="space-y-4">{content}</div> : <Card>{content}</Card>
}

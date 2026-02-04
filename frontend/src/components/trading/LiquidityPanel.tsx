import React, { useState } from 'react'
import { Card, CardHeader, Button } from '../common'
import { formatCrypto, formatPercentage, parseNumericInput, isValidAmount } from '../../utils'
import type { PoolInfo, LPPosition } from '../../types'

interface LiquidityPanelProps {
  pool: PoolInfo | null
  lpPosition: LPPosition | null
  onAddLiquidity: (baseAmount: string, quoteAmount: string, slippage: number) => Promise<void>
  onRemoveLiquidity: (percentage: number, slippage: number) => Promise<void>
  isLoading?: boolean
  baseBalance?: string
  quoteBalance?: string
}

export const LiquidityPanel: React.FC<LiquidityPanelProps> = ({
  pool,
  lpPosition,
  onAddLiquidity,
  onRemoveLiquidity,
  isLoading = false,
  baseBalance = '0',
  quoteBalance = '0',
}) => {
  const [activeTab, setActiveTab] = useState<'add' | 'remove'>('add')
  const [baseAmount, setBaseAmount] = useState('')
  const [quoteAmount, setQuoteAmount] = useState('')
  const [removePercentage, setRemovePercentage] = useState(25)
  const [slippage] = useState(0.5)

  // Calculate proportional amounts based on pool ratio
  const handleBaseAmountChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setBaseAmount(cleaned)

    if (pool && cleaned && isValidAmount(cleaned)) {
      const price = parseFloat(pool.current_price)
      const proportionalQuote = (parseFloat(cleaned) * price).toFixed(8)
      setQuoteAmount(proportionalQuote)
    } else {
      setQuoteAmount('')
    }
  }

  const handleQuoteAmountChange = (value: string) => {
    const cleaned = parseNumericInput(value)
    setQuoteAmount(cleaned)

    if (pool && cleaned && isValidAmount(cleaned)) {
      const price = parseFloat(pool.current_price)
      const proportionalBase = (parseFloat(cleaned) / price).toFixed(8)
      setBaseAmount(proportionalBase)
    } else {
      setBaseAmount('')
    }
  }

  const handleAddLiquidity = async () => {
    if (!baseAmount || !quoteAmount) return
    await onAddLiquidity(baseAmount, quoteAmount, slippage / 100)
    setBaseAmount('')
    setQuoteAmount('')
  }

  const handleRemoveLiquidity = async () => {
    await onRemoveLiquidity(removePercentage, slippage / 100)
  }

  const removePercentageOptions = [25, 50, 75, 100]

  return (
    <Card>
      <CardHeader
        title="Liquidity"
        subtitle="Add or remove liquidity from the pool"
      />

      {!pool ? (
        <div className="text-center py-8 text-text-secondary">
          Select a trading pair to manage liquidity
        </div>
      ) : (
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex border-b border-border-default">
            <button
              type="button"
              onClick={() => setActiveTab('add')}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'add'
                  ? 'text-accent-blue border-accent-blue'
                  : 'text-text-secondary border-transparent hover:text-text-primary'
              }`}
            >
              Add Liquidity
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('remove')}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'remove'
                  ? 'text-accent-blue border-accent-blue'
                  : 'text-text-secondary border-transparent hover:text-text-primary'
              }`}
            >
              Remove Liquidity
            </button>
          </div>

          {/* Your Position */}
          {lpPosition && parseFloat(lpPosition.lp_shares) > 0 && (
            <div className="p-4 bg-accent-blue/10 border border-accent-blue/20 rounded-lg">
              <h4 className="text-sm font-medium text-accent-blue mb-3">Your Position</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-text-tertiary">LP Shares</p>
                  <p className="font-medium text-text-primary">{formatCrypto(lpPosition.lp_shares)}</p>
                </div>
                <div>
                  <p className="text-text-tertiary">Pool Share</p>
                  <p className="font-medium text-text-primary">{formatPercentage(lpPosition.share_percentage)}</p>
                </div>
                <div>
                  <p className="text-text-tertiary">{pool.base}</p>
                  <p className="font-medium text-text-primary">{formatCrypto(lpPosition.base_amount)}</p>
                </div>
                <div>
                  <p className="text-text-tertiary">{pool.quote}</p>
                  <p className="font-medium text-text-primary">{formatCrypto(lpPosition.quote_amount)}</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'add' ? (
            /* Add Liquidity Form */
            <div className="space-y-4">
              {/* Base Token Input */}
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-text-secondary">{pool.base}</span>
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(baseBalance)}
                  </span>
                </div>
                <input
                  type="text"
                  value={baseAmount}
                  onChange={(e) => handleBaseAmountChange(e.target.value)}
                  placeholder="0.00"
                  className="w-full bg-transparent text-xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
              </div>

              <div className="flex justify-center">
                <div className="w-8 h-8 bg-bg-tertiary rounded-full flex items-center justify-center">
                  <span className="text-text-tertiary">+</span>
                </div>
              </div>

              {/* Quote Token Input */}
              <div className="p-4 bg-bg-tertiary rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-text-secondary">{pool.quote}</span>
                  <span className="text-xs text-text-tertiary">
                    Balance: {formatCrypto(quoteBalance)}
                  </span>
                </div>
                <input
                  type="text"
                  value={quoteAmount}
                  onChange={(e) => handleQuoteAmountChange(e.target.value)}
                  placeholder="0.00"
                  className="w-full bg-transparent text-xl font-medium text-text-primary placeholder-text-tertiary focus:outline-none"
                />
              </div>

              <Button
                fullWidth
                size="lg"
                variant="success"
                onClick={handleAddLiquidity}
                isLoading={isLoading}
                disabled={!baseAmount || !quoteAmount || !isValidAmount(baseAmount)}
              >
                Add Liquidity
              </Button>
            </div>
          ) : (
            /* Remove Liquidity Form */
            <div className="space-y-4">
              {!lpPosition || parseFloat(lpPosition.lp_shares) === 0 ? (
                <div className="text-center py-8 text-text-secondary">
                  You don't have any liquidity to remove
                </div>
              ) : (
                <>
                  {/* Percentage Selector */}
                  <div>
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-sm text-text-secondary">Amount to Remove</span>
                      <span className="text-lg font-bold text-text-primary">{removePercentage}%</span>
                    </div>
                    
                    {/* Slider */}
                    <input
                      type="range"
                      min="1"
                      max="100"
                      value={removePercentage}
                      onChange={(e) => setRemovePercentage(parseInt(e.target.value))}
                      className="w-full h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-blue"
                    />

                    {/* Quick buttons */}
                    <div className="flex gap-2 mt-3">
                      {removePercentageOptions.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => setRemovePercentage(option)}
                          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                            removePercentage === option
                              ? 'bg-accent-blue text-white'
                              : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                          }`}
                        >
                          {option}%
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Preview */}
                  <div className="p-4 bg-bg-tertiary rounded-lg space-y-2">
                    <p className="text-sm text-text-secondary mb-3">You will receive (estimated)</p>
                    <div className="flex justify-between items-center">
                      <span className="text-text-primary">{pool.base}</span>
                      <span className="font-medium text-text-primary">
                        {formatCrypto(
                          (parseFloat(lpPosition.base_amount) * removePercentage / 100).toString()
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-text-primary">{pool.quote}</span>
                      <span className="font-medium text-text-primary">
                        {formatCrypto(
                          (parseFloat(lpPosition.quote_amount) * removePercentage / 100).toString()
                        )}
                      </span>
                    </div>
                  </div>

                  <Button
                    fullWidth
                    size="lg"
                    variant="danger"
                    onClick={handleRemoveLiquidity}
                    isLoading={isLoading}
                  >
                    Remove Liquidity
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

import React, { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTrading, useTradingInitialization } from '../../hooks'
import { Card, CardHeader } from '../common'
import { toMarketId, getDisplayName, groupSymbolsByEngine } from '../../utils'
import type { Symbol } from '../../types'

// Market Card Component
const MarketCard: React.FC<{
  symbol: Symbol
  isSelected: boolean
  onSelect: () => void
}> = ({ symbol, isSelected, onSelect }) => {
  return (
    <button
      onClick={onSelect}
      className={`w-full p-3 rounded-lg border text-left transition-all ${
        isSelected
          ? 'bg-accent-blue/10 border-accent-blue'
          : 'bg-bg-tertiary border-border-default hover:border-border-hover'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center">
            <span className="text-xs font-bold text-accent-blue">
              {symbol.base?.charAt(0)}
            </span>
          </div>
          <div>
            <p className="font-medium text-text-primary">{getDisplayName(symbol)}</p>
            <p className="text-xs text-text-tertiary">{symbol.market?.toUpperCase() || 'SPOT'}</p>
          </div>
        </div>
        {symbol.current_price && (
          <span className="text-sm text-text-secondary">
            ${symbol.current_price.toFixed(2)}
          </span>
        )}
      </div>
    </button>
  )
}

export const TradingPage: React.FC = () => {
  const navigate = useNavigate()
  const { symbols, loadSymbols } = useTrading()

  // Initialize trading data
  useTradingInitialization()

  // Group symbols by engine type
  const { amm: ammSymbols, clob: clobSymbols } = useMemo(
    () => groupSymbolsByEngine(symbols),
    [symbols]
  )

  // Load symbols on mount
  useEffect(() => {
    if (symbols.length === 0) {
      loadSymbols()
    }
  }, [symbols.length, loadSymbols])

  const handleSymbolSelect = (symbol: Symbol) => {
    navigate(`/trade/${toMarketId(symbol)}`)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Trade</h1>
        <p className="text-text-secondary mt-1">
          Select a market to start trading
        </p>
      </div>

      {/* Two Column Market Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AMM Pools */}
        <Card>
          <CardHeader
            title="AMM Pools"
            subtitle={`${ammSymbols.length} available pools`}
          />
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {ammSymbols.length > 0 ? (
              ammSymbols.map((symbol) => (
                <MarketCard
                  key={symbol.symbol}
                  symbol={symbol}
                  isSelected={false}
                  onSelect={() => handleSymbolSelect(symbol)}
                />
              ))
            ) : (
              <p className="text-center text-text-tertiary py-4">No AMM pools available</p>
            )}
          </div>
        </Card>

        {/* Order Book Markets */}
        <Card>
          <CardHeader
            title="Order Book Markets"
            subtitle={`${clobSymbols.length} available pairs`}
          />
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {clobSymbols.length > 0 ? (
              clobSymbols.map((symbol) => (
                <MarketCard
                  key={symbol.symbol}
                  symbol={symbol}
                  isSelected={false}
                  onSelect={() => handleSymbolSelect(symbol)}
                />
              ))
            ) : (
              <p className="text-center text-text-tertiary py-4">No order book markets available</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

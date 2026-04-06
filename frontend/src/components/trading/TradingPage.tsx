import React, { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTrading, useTradingInitialization } from '../../hooks'
import { Card, CardHeader } from '../common'
import { getDisplayName, groupSymbolsByEngine, toSpotTradePath } from '../../utils'
import type { Symbol } from '../../types'

export const TradingPage: React.FC = () => {
  const navigate = useNavigate()
  const { symbols, loadSymbols } = useTrading()

  useTradingInitialization()

  // Only show CLOB spot markets
  const spotMarkets = useMemo(
    () => groupSymbolsByEngine(symbols).clob,
    [symbols]
  )

  useEffect(() => {
    if (symbols.length === 0) {
      loadSymbols()
    }
  }, [symbols.length, loadSymbols])

  const handleSelect = (symbol: Symbol) => {
    navigate(toSpotTradePath(symbol))
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Spot Markets</h1>
        <p className="text-text-secondary mt-1">
          Order book trading — select a pair to start
        </p>
      </div>

      <Card>
        <CardHeader
          title="Order Book Markets"
          subtitle={`${spotMarkets.length} available pairs`}
        />
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {spotMarkets.length > 0 ? (
            spotMarkets.map((symbol) => (
              <button
                key={symbol.symbol}
                onClick={() => handleSelect(symbol)}
                className="w-full p-3 rounded-lg border text-left transition-all bg-bg-tertiary border-border-default hover:border-border-hover"
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
                      <p className="text-xs text-text-tertiary">
                        Order Book • {symbol.market?.toUpperCase() || 'SPOT'}
                      </p>
                    </div>
                  </div>
                  {symbol.current_price != null && (
                    <span className="text-sm text-text-secondary font-mono">
                      {Number(symbol.current_price).toFixed(4)}
                    </span>
                  )}
                </div>
              </button>
            ))
          ) : (
            <p className="text-center text-text-tertiary py-8">No spot markets available</p>
          )}
        </div>
      </Card>
    </div>
  )
}

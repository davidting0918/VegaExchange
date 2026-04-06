import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTrading, useTradingInitialization } from '../../hooks'
import { toSpotTradePath, groupSymbolsByEngine } from '../../utils'
import { LoadingSpinner } from '../common'

/**
 * /trade/spot — auto-redirects to the first available CLOB spot market.
 * No market list page; Binance-style direct entry to trading UI.
 */
export const TradingPage: React.FC = () => {
  const navigate = useNavigate()
  const { symbols, loadSymbols } = useTrading()

  useTradingInitialization()

  useEffect(() => {
    if (symbols.length === 0) {
      loadSymbols()
    }
  }, [symbols.length, loadSymbols])

  useEffect(() => {
    if (symbols.length === 0) return
    const clob = groupSymbolsByEngine(symbols).clob
    if (clob.length > 0) {
      navigate(toSpotTradePath(clob[0]), { replace: true })
    }
  }, [symbols, navigate])

  // Show loading while fetching symbols, or empty state if none
  const clob = groupSymbolsByEngine(symbols).clob
  if (symbols.length > 0 && clob.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-text-secondary">No spot markets available.</p>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <LoadingSpinner size="lg" />
    </div>
  )
}

import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { marketService } from '../../api'
import { formatNumber, toSpotTradePath, groupSymbolsByEngine } from '../../utils'
import type { Symbol as SymbolType, Trade } from '../../types'

interface MarketPairsSidebarProps {
  currentSymbol: string
  trades: Trade[]
  tradesLoading: boolean
}

export const MarketPairsSidebar: React.FC<MarketPairsSidebarProps> = ({
  currentSymbol,
  trades,
  tradesLoading,
}) => {
  const navigate = useNavigate()
  const [symbols, setSymbols] = useState<SymbolType[]>([])
  const [search, setSearch] = useState('')
  const [quoteFilter, setQuoteFilter] = useState('ALL')

  const loadSymbols = useCallback(async () => {
    try {
      const response = await marketService.getSymbols()
      if (response.success && response.data) {
        const clob = groupSymbolsByEngine(response.data as SymbolType[]).clob
        setSymbols(clob)
      }
    } catch (err) {
      console.error('Failed to load symbols:', err)
    }
  }, [])

  useEffect(() => { loadSymbols() }, [loadSymbols])

  // Refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadSymbols, 30000)
    return () => clearInterval(interval)
  }, [loadSymbols])

  // Get unique quote currencies for tabs
  const quoteCurrencies = useMemo(() => {
    const quotes = new Set(symbols.map(s => s.quote))
    return Array.from(quotes)
  }, [symbols])

  // Filter symbols
  const filteredSymbols = useMemo(() => {
    let filtered = symbols
    if (quoteFilter !== 'ALL') {
      filtered = filtered.filter(s => s.quote === quoteFilter)
    }
    if (search) {
      const q = search.toUpperCase()
      filtered = filtered.filter(s =>
        s.base?.toUpperCase().includes(q) || s.quote?.toUpperCase().includes(q)
      )
    }
    return filtered
  }, [symbols, quoteFilter, search])

  const handleSelect = (symbol: SymbolType) => {
    navigate(toSpotTradePath(symbol), { replace: true })
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-2 border-b border-border-default">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search"
          className="w-full px-2 py-1.5 bg-bg-tertiary border border-border-default rounded text-xs text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue"
        />
      </div>

      {/* Quote currency tabs */}
      <div className="flex gap-1 px-2 py-1.5 border-b border-border-default">
        {['ALL', ...quoteCurrencies].map(q => (
          <button
            key={q}
            onClick={() => setQuoteFilter(q)}
            className={`px-2 py-0.5 text-xs rounded ${
              quoteFilter === q
                ? 'text-accent-blue font-medium'
                : 'text-text-tertiary hover:text-text-secondary'
            }`}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Pair header */}
      <div className="flex items-center justify-between px-3 py-1.5 text-xs text-text-tertiary border-b border-border-default">
        <span>Pair</span>
        <span>Price</span>
      </div>

      {/* Pair list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {filteredSymbols.map(s => {
          const isActive = s.symbol === currentSymbol
          return (
            <button
              key={s.symbol}
              onClick={() => handleSelect(s)}
              className={`w-full flex items-center justify-between px-3 py-1.5 text-xs transition-colors ${
                isActive
                  ? 'bg-bg-tertiary text-text-primary'
                  : 'text-text-secondary hover:bg-bg-tertiary/50 hover:text-text-primary'
              }`}
            >
              <span className="font-medium">
                <span className="text-text-primary">{s.base}</span>
                <span className="text-text-tertiary">/{s.quote}</span>
              </span>
              <span className="font-mono">
                {s.current_price != null ? formatNumber(Number(s.current_price), 6) : '—'}
              </span>
            </button>
          )
        })}
        {filteredSymbols.length === 0 && (
          <div className="text-center py-4 text-text-tertiary text-xs">No pairs found</div>
        )}
      </div>

      {/* Recent Trades section */}
      <div className="border-t border-border-default">
        <div className="px-3 py-1.5 text-xs text-text-tertiary font-medium border-b border-border-default">
          Recent Trades
        </div>
        <div className="flex items-center justify-between px-3 py-1 text-xs text-text-tertiary">
          <span>Price</span>
          <span>Qty</span>
          <span>Time</span>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: 200 }}>
          {tradesLoading ? (
            <div className="text-center py-4 text-text-tertiary text-xs">Loading...</div>
          ) : trades.length === 0 ? (
            <div className="text-center py-4 text-text-tertiary text-xs">No trades</div>
          ) : (
            trades.slice(0, 20).map((t, i) => {
              const side = typeof t.side === 'number' ? (t.side === 0 ? 'buy' : 'sell') : t.side
              return (
                <div key={t.trade_id || i} className="flex items-center justify-between px-3 py-0.5 text-xs">
                  <span className={`font-mono ${side === 'buy' ? 'text-accent-green' : 'text-accent-red'}`}>
                    {formatNumber(Number(t.price), 6)}
                  </span>
                  <span className="text-text-secondary font-mono">
                    {formatNumber(Number(t.quantity), 4)}
                  </span>
                  <span className="text-text-tertiary">
                    {t.created_at ? new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

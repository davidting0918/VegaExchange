import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, LoadingSpinner } from '../common'
import { marketService } from '../../api'
import { formatNumber, toPoolPath, getDisplayName } from '../../utils'
import type { Symbol as SymbolType } from '../../types'

export const PoolsListPage: React.FC = () => {
  const navigate = useNavigate()
  const [pools, setPools] = useState<SymbolType[]>([])
  const [loading, setLoading] = useState(true)

  const loadPools = useCallback(async () => {
    try {
      const response = await marketService.getSymbols()
      if (response.success && response.data) {
        // Filter to AMM pools only (engine_type=0)
        const ammPools = (response.data as SymbolType[]).filter(
          (s) => s.engine_type === 0
        )
        setPools(ammPools)
      }
    } catch (err) {
      console.error('Failed to load pools:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPools()
  }, [loadPools])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Pools</h1>
        <p className="text-text-secondary mt-1">AMM liquidity pools — swap tokens and earn fees.</p>
      </div>

      {pools.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-text-secondary">No active pools available.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pools.map((pool) => (
            <button
              key={pool.symbol_id ?? pool.symbol}
              onClick={() => navigate(toPoolPath(pool))}
              className="w-full text-left p-5 bg-bg-secondary border border-border-default rounded-lg hover:border-border-hover transition-all group"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-accent-green/10 flex items-center justify-center">
                    <span className="text-sm font-bold text-accent-green">
                      {pool.base?.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-text-primary group-hover:text-accent-blue transition-colors">
                      {getDisplayName(pool)}
                    </p>
                    <p className="text-xs text-text-tertiary">AMM Pool</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-text-tertiary text-xs">Price</p>
                  <p className="text-text-primary font-mono">
                    {formatNumber(pool.current_price || 0, 6)}
                  </p>
                </div>
                <div>
                  <p className="text-text-tertiary text-xs">Fee Rate</p>
                  <p className="text-text-primary font-mono">
                    {(((pool as unknown as { fee_rate?: number }).fee_rate || 0.003) * 100).toFixed(2)}%
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

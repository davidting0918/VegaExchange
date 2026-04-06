import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../common'
import { marketService } from '../../api'
import { toPoolPath } from '../../utils'
import type { Symbol as SymbolType } from '../../types'

/**
 * /pools — auto-redirects to the first available AMM pool.
 * No pool list page; direct entry to pool detail/swap UI.
 */
export const PoolsListPage: React.FC = () => {
  const navigate = useNavigate()
  const [pools, setPools] = useState<SymbolType[]>([])
  const [loading, setLoading] = useState(true)

  const loadPools = useCallback(async () => {
    try {
      const response = await marketService.getSymbols()
      if (response.success && response.data) {
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

  useEffect(() => {
    if (loading || pools.length === 0) return
    navigate(toPoolPath(pools[0]), { replace: true })
  }, [loading, pools, navigate])

  if (!loading && pools.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-text-secondary">No active pools available.</p>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <LoadingSpinner size="lg" />
    </div>
  )
}

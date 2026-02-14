import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useSelector } from 'react-redux'
import { Card } from '../common'
import { VolumeBarChart, PriceLineChart } from '../charts'
import { tradeService } from '../../api'
import type { PoolInfo } from '../../types'
import type { LineData } from 'lightweight-charts'
import type { RootState } from '../../store'

type ChartType = 'price' | 'volume' | 'liquidity'
type TimeRange = '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL'

interface PoolChartSectionProps {
  pool: PoolInfo | null
  /** Controlled time range from URL; when provided, parent owns state. */
  timeRange?: TimeRange
  onTimeRangeChange?: (range: TimeRange) => void
}

export const PoolChartSection: React.FC<PoolChartSectionProps> = ({
  pool,
  timeRange: controlledTimeRange,
  onTimeRangeChange,
}) => {
  const [chartType, setChartType] = useState<ChartType>('price')
  const [internalTimeRange, setInternalTimeRange] = useState<TimeRange>('1D')
  const isControlled = controlledTimeRange != null && onTimeRangeChange != null
  const timeRange = isControlled ? controlledTimeRange : internalTimeRange
  const setTimeRange = isControlled ? onTimeRangeChange : setInternalTimeRange
  const timeRangeRef = useRef<TimeRange>(timeRange)
  timeRangeRef.current = timeRange
  const [volumeBuckets, setVolumeBuckets] = useState<{ time: string; volume: number }[]>([])
  const [pricePoints, setPricePoints] = useState<{ time: string; price: number }[]>([])
  const [priceRange, setPriceRange] = useState<{ from: string; to: string } | null>(null)
  const [chartError, setChartError] = useState<string | null>(null)

  const chartTypes: { id: ChartType; label: string }[] = [
    { id: 'price', label: 'Price' },
    { id: 'volume', label: 'Volume' },
    { id: 'liquidity', label: 'Liquidity' },
  ]

  const timeRanges: TimeRange[] = ['1H', '1D', '1W', '1M', '1Y', 'ALL']

  const fetchChartData = React.useCallback(() => {
    if (!pool?.symbol) return
    setChartError(null)
    const period = timeRange
    if (chartType === 'price') {
      tradeService
        .getPoolPriceHistory(pool.symbol, period)
        .then((res) => {
          if (import.meta.env.DEV) {
            console.log('[PoolChart] price history', { period, res: res.success ? { pricesCount: res.data?.prices?.length, range: res.data?.range, sample: res.data?.prices?.slice(0, 3) } : res })
          }
          if (timeRangeRef.current !== period) return
          if (res.success && res.data?.prices) {
            setPricePoints(res.data.prices)
            setPriceRange(res.data.range ?? null)
          } else {
            setPricePoints([])
            setPriceRange(null)
          }
        })
        .catch(() => {
          if (timeRangeRef.current !== period) return
          setPricePoints([])
          setPriceRange(null)
          setChartError('Failed to load price history')
        })
    } else {
      tradeService
        .getPoolVolumeChart(pool.symbol, period)
        .then((res) => {
          if (timeRangeRef.current !== period) return
          if (res.success && res.data?.buckets) setVolumeBuckets(res.data.buckets)
          else setVolumeBuckets([])
        })
        .catch(() => {
          if (timeRangeRef.current !== period) return
          setVolumeBuckets([])
          setChartError('Failed to load volume data')
        })
    }
  }, [pool?.symbol, chartType, timeRange])

  // Initial fetch + refetch when symbol / chartType / timeRange change (not on every pool update)
  useEffect(() => {
    fetchChartData()
  }, [fetchChartData])

  const lastPricePoint = useSelector((state: RootState) =>
    pool?.symbol ? state.trading.lastPricePointBySymbol[pool.symbol] ?? null : null
  )

  // Append WebSocket price point to chart without refetching
  useEffect(() => {
    if (chartType !== 'price' || !pool?.symbol || !lastPricePoint) return
    setPricePoints((prev) => {
      const t = lastPricePoint.time
      if (prev.some((p) => p.time === t)) return prev
      const next = [...prev, { time: t, price: lastPricePoint.price }].sort(
        (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()
      )
      return next
    })
  }, [chartType, pool?.symbol, lastPricePoint])

  const volumeData = useMemo(
    () =>
      volumeBuckets.map((b) => ({
        time: b.time.slice(0, 19).replace('T', ' '),
        volume: b.volume,
      })),
    [volumeBuckets]
  )

  // Chart requires strictly ascending time with no duplicates; dedupe by time (keep last)
  const priceLineData: LineData[] = useMemo(() => {
    const withTime = pricePoints.map((p) => ({
      time: new Date(p.time).getTime() / 1000,
      value: p.price,
    }))
    withTime.sort((a, b) => a.time - b.time)
    const deduped: LineData[] = []
    for (const pt of withTime) {
      const t = pt.time as unknown as LineData['time']
      if (deduped.length > 0 && deduped[deduped.length - 1].time === t) {
        (deduped[deduped.length - 1] as { time: LineData['time']; value: number }).value = pt.value
      } else {
        deduped.push({ time: t, value: pt.value })
      }
    }
    return deduped
  }, [pricePoints])

  const showVolumeChart = chartType === 'volume' || chartType === 'liquidity'
  const showPriceChart = chartType === 'price'

  return (
    <Card className="overflow-hidden">
      <div className="p-4 border-b border-border-default">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex gap-2">
            {chartTypes.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setChartType(id)}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  chartType === id
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {timeRanges.map((range) => (
              <button
                key={range}
                type="button"
                onClick={() => setTimeRange(range)}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                  timeRange === range
                    ? 'bg-bg-tertiary text-text-primary'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="pt-4 min-h-[300px] bg-bg-tertiary/30">
        {!pool ? (
          <div className="flex items-center justify-center h-[300px] text-text-tertiary text-sm">
            —
          </div>
        ) : chartError ? (
          <div className="flex items-center justify-center h-[300px] text-accent-red text-sm">
            {chartError}
          </div>
        ) : showPriceChart ? (
          priceLineData.length > 0 ? (
            <div className="px-2 pb-2">
              <PriceLineChart
                data={priceLineData}
                height={300}
                dataSetKey={`price-${timeRange}`}
                visibleRange={priceRange}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-[300px] text-text-tertiary text-sm">
              No price history for this period
            </div>
          )
        ) : showVolumeChart ? (
          volumeData.length > 0 ? (
            <div className="px-4 pb-2">
              <VolumeBarChart data={volumeData} height={300} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-[300px] text-text-tertiary text-sm">
              No volume data for this period
            </div>
          )
        ) : null}
      </div>
    </Card>
  )
}

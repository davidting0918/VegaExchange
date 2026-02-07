import React, { useState, useEffect, useMemo } from 'react'
import { Card } from '../common'
import { VolumeBarChart, PriceLineChart } from '../charts'
import { tradeService } from '../../api'
import type { PoolInfo } from '../../types'
import type { LineData } from 'lightweight-charts'

type ChartType = 'price' | 'volume' | 'liquidity'
type TimeRange = '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL'

interface PoolChartSectionProps {
  pool: PoolInfo | null
}

export const PoolChartSection: React.FC<PoolChartSectionProps> = ({ pool }) => {
  const [chartType, setChartType] = useState<ChartType>('price')
  const [timeRange, setTimeRange] = useState<TimeRange>('1D')
  const [volumeBuckets, setVolumeBuckets] = useState<{ time: string; volume: number }[]>([])
  const [pricePoints, setPricePoints] = useState<{ time: string; price: number }[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [chartError, setChartError] = useState<string | null>(null)

  const chartTypes: { id: ChartType; label: string }[] = [
    { id: 'price', label: 'Price' },
    { id: 'volume', label: 'Volume' },
    { id: 'liquidity', label: 'Liquidity' },
  ]

  const timeRanges: TimeRange[] = ['1H', '1D', '1W', '1M', '1Y', 'ALL']

  useEffect(() => {
    if (!pool?.symbol) return
    setChartLoading(true)
    setChartError(null)
    const period = timeRange
    if (chartType === 'price') {
      tradeService
        .getPoolPriceHistory(pool.symbol, period)
        .then((res) => {
          if (res.success && res.data?.prices) setPricePoints(res.data.prices)
          else setPricePoints([])
        })
        .catch(() => {
          setPricePoints([])
          setChartError('Failed to load price history')
        })
        .finally(() => setChartLoading(false))
    } else {
      tradeService
        .getPoolVolumeChart(pool.symbol, period)
        .then((res) => {
          if (res.success && res.data?.buckets) setVolumeBuckets(res.data.buckets)
          else setVolumeBuckets([])
        })
        .catch(() => {
          setVolumeBuckets([])
          setChartError('Failed to load volume data')
        })
        .finally(() => setChartLoading(false))
    }
  }, [pool?.symbol, chartType, timeRange])

  const volumeData = useMemo(
    () =>
      volumeBuckets.map((b) => ({
        time: b.time.slice(0, 19).replace('T', ' '),
        volume: b.volume,
      })),
    [volumeBuckets]
  )

  const priceLineData: LineData[] = useMemo(
    () =>
      pricePoints.map((p) => ({
        time: (new Date(p.time).getTime() / 1000) as unknown as LineData['time'],
        value: p.price,
      })),
    [pricePoints]
  )

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
        ) : chartLoading ? (
          <div className="flex items-center justify-center h-[300px] text-text-tertiary text-sm">
            Loading…
          </div>
        ) : chartError ? (
          <div className="flex items-center justify-center h-[300px] text-accent-red text-sm">
            {chartError}
          </div>
        ) : showPriceChart ? (
          priceLineData.length > 0 ? (
            <div className="px-2 pb-2">
              <PriceLineChart data={priceLineData} height={300} />
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

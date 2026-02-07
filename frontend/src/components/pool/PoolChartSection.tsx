import React, { useState } from 'react'
import { Card } from '../common'
import type { PoolInfo } from '../../types'

type ChartType = 'price' | 'volume' | 'liquidity'
type TimeRange = '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL'

interface PoolChartSectionProps {
  pool: PoolInfo | null
}

export const PoolChartSection: React.FC<PoolChartSectionProps> = ({ pool }) => {
  const [chartType, setChartType] = useState<ChartType>('price')
  const [timeRange, setTimeRange] = useState<TimeRange>('1D')

  const chartTypes: { id: ChartType; label: string }[] = [
    { id: 'price', label: 'Price' },
    { id: 'volume', label: 'Volume' },
    { id: 'liquidity', label: 'Liquidity' },
  ]

  const timeRanges: TimeRange[] = ['1H', '1D', '1W', '1M', '1Y', 'ALL']

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
      <div className="pt-4 min-h-[300px] flex items-center justify-center text-text-tertiary text-sm bg-bg-tertiary/30">
        {pool ? (
          <span>
            {chartType.charAt(0).toUpperCase() + chartType.slice(1)} chart ({timeRange}) — Coming soon
          </span>
        ) : (
          <span>—</span>
        )}
      </div>
    </Card>
  )
}

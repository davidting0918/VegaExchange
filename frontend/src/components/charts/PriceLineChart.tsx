import React, { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, LineData, ColorType, AreaSeries } from 'lightweight-charts'

interface PriceLineChartProps {
  data: LineData[]
  height?: number
  lineColor?: string
  areaTopColor?: string
  areaBottomColor?: string
  /** When this changes (e.g. chartType-timeRange), fit content. Preserves zoom on refetch when unchanged. */
  dataSetKey?: string
  /** Optional visible time range (UTC ISO strings). When set, chart x-axis spans this range so 1W always shows 7 days. */
  visibleRange?: { from: string; to: string } | null
}

export const PriceLineChart: React.FC<PriceLineChartProps> = ({
  data,
  height = 300,
  lineColor = '#3B82F6',
  areaTopColor = 'rgba(59, 130, 246, 0.4)',
  areaBottomColor = 'rgba(59, 130, 246, 0.0)',
  dataSetKey,
  visibleRange,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9CA3AF',
      },
      grid: {
        vertLines: { color: 'rgba(75, 85, 99, 0.3)' },
        horzLines: { color: 'rgba(75, 85, 99, 0.3)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      rightPriceScale: {
        borderColor: 'rgba(75, 85, 99, 0.5)',
      },
      timeScale: {
        borderColor: 'rgba(75, 85, 99, 0.5)',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: {
          color: 'rgba(59, 130, 246, 0.5)',
          labelBackgroundColor: '#3B82F6',
        },
        horzLine: {
          color: 'rgba(59, 130, 246, 0.5)',
          labelBackgroundColor: '#3B82F6',
        },
      },
    })

    // Create area series using new API
    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: lineColor,
      topColor: areaTopColor,
      bottomColor: areaBottomColor,
      lineWidth: 2,
    })

    chartRef.current = chart
    seriesRef.current = areaSeries

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [height, lineColor, areaTopColor, areaBottomColor])

  // Update data when it changes – preserve visible range on refetch (don't call fitContent)
  const hasFittedRef = useRef(false)
  const lastDataSetKeyRef = useRef<string | undefined>(undefined)
  const rangeFrom = visibleRange?.from ?? null
  const rangeTo = visibleRange?.to ?? null
  useEffect(() => {
    if (!seriesRef.current || data.length === 0) return
    seriesRef.current.setData(data)
    const keyChanged = dataSetKey !== lastDataSetKeyRef.current
    const shouldFit = !hasFittedRef.current || keyChanged
    if (shouldFit) {
      const ts = chartRef.current?.timeScale()
      if (ts) {
        if (rangeFrom && rangeTo) {
          const fromSec = Math.floor(new Date(rangeFrom).getTime() / 1000)
          const toSec = Math.floor(new Date(rangeTo).getTime() / 1000)
          ts.setVisibleRange({ from: fromSec as LineData['time'], to: toSec as LineData['time'] })
        } else {
          ts.fitContent()
        }
      }
      hasFittedRef.current = true
      lastDataSetKeyRef.current = dataSetKey
    }
  }, [data, dataSetKey, rangeFrom, rangeTo])

  return (
    <div
      ref={chartContainerRef}
      className="w-full"
      style={{ height: `${height}px` }}
    />
  )
}

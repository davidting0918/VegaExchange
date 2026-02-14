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
}

export const PriceLineChart: React.FC<PriceLineChartProps> = ({
  data,
  height = 300,
  lineColor = '#3B82F6',
  areaTopColor = 'rgba(59, 130, 246, 0.4)',
  areaBottomColor = 'rgba(59, 130, 246, 0.0)',
  dataSetKey,
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
  useEffect(() => {
    if (!seriesRef.current || data.length === 0) return
    seriesRef.current.setData(data)
    // fitContent on first load or when dataSetKey changes (e.g. time range); refetch keeps zoom
    const keyChanged = dataSetKey !== lastDataSetKeyRef.current
    const shouldFit = !hasFittedRef.current || keyChanged
    if (shouldFit) {
      chartRef.current?.timeScale().fitContent()
      hasFittedRef.current = true
      lastDataSetKeyRef.current = dataSetKey
    }
  }, [data, dataSetKey])

  return (
    <div
      ref={chartContainerRef}
      className="w-full"
      style={{ height: `${height}px` }}
    />
  )
}

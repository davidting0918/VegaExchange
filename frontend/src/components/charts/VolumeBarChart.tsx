import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { VolumeDataPoint } from '../../types'

interface VolumeBarChartProps {
  data: VolumeDataPoint[]
  height?: number
  barColor?: string
}

export const VolumeBarChart: React.FC<VolumeBarChartProps> = ({
  data,
  height = 200,
  barColor = '#3B82F6',
}) => {
  // Format volume for display
  const formatVolume = (value: number): string => {
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)}M`
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(2)}K`
    }
    return value.toFixed(2)
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(75, 85, 99, 0.3)"
          vertical={false}
        />
        <XAxis
          dataKey="time"
          tick={{ fill: '#9CA3AF', fontSize: 12 }}
          axisLine={{ stroke: 'rgba(75, 85, 99, 0.5)' }}
          tickLine={{ stroke: 'rgba(75, 85, 99, 0.5)' }}
        />
        <YAxis
          tickFormatter={formatVolume}
          tick={{ fill: '#9CA3AF', fontSize: 12 }}
          axisLine={{ stroke: 'rgba(75, 85, 99, 0.5)' }}
          tickLine={{ stroke: 'rgba(75, 85, 99, 0.5)' }}
          width={60}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1F2937',
            border: '1px solid rgba(75, 85, 99, 0.5)',
            borderRadius: '8px',
            color: '#F3F4F6',
          }}
          formatter={(value: number | undefined) => {
            if (value === undefined) return ['-', 'Volume']
            return [formatVolume(value), 'Volume']
          }}
          labelStyle={{ color: '#9CA3AF' }}
        />
        <Bar
          dataKey="volume"
          fill={barColor}
          radius={[4, 4, 0, 0]}
          maxBarSize={50}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

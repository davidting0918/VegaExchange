import React from 'react'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts'

interface LPPieChartData {
  name: string
  value: number
  color: string
}

interface LPPieChartProps {
  userShare: number // Percentage 0-100
  height?: number
}

const COLORS = {
  user: '#3B82F6',
  others: '#374151',
}

export const LPPieChart: React.FC<LPPieChartProps> = ({
  userShare,
  height = 200,
}) => {
  const data: LPPieChartData[] = [
    { name: 'Your Share', value: userShare, color: COLORS.user },
    { name: 'Others', value: 100 - userShare, color: COLORS.others },
  ]

  const formatPercentage = (value: number): string => {
    return `${value.toFixed(2)}%`
  }

  // Custom label renderer
  interface LabelProps {
    cx?: number
    cy?: number
    midAngle?: number
    innerRadius?: number
    outerRadius?: number
    percent?: number
  }

  const renderCustomLabel = ({
    cx = 0,
    cy = 0,
    midAngle = 0,
    innerRadius = 0,
    outerRadius = 0,
    percent = 0,
  }: LabelProps) => {
    if (percent < 0.05) return null // Don't show label if less than 5%
    
    const RADIAN = Math.PI / 180
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(-midAngle * RADIAN)
    const y = cy + radius * Math.sin(-midAngle * RADIAN)

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={12}
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(1)}%`}
      </text>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={70}
          paddingAngle={2}
          dataKey="value"
          labelLine={false}
          label={renderCustomLabel}
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: '#1F2937',
            border: '1px solid rgba(75, 85, 99, 0.5)',
            borderRadius: '8px',
            color: '#F3F4F6',
          }}
          formatter={(value: number | undefined) => {
            if (value === undefined) return ['-', 'Share']
            return [formatPercentage(value), 'Share']
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => (
            <span style={{ color: '#9CA3AF', fontSize: '12px' }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

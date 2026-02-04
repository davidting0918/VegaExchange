import React from 'react'
import { Card } from '../common'
import { formatCrypto } from '../../utils'
import type { Balance } from '../../types'

interface BalanceCardProps {
  balance: Balance
}

// Token icons mapping
const tokenIcons: Record<string, string> = {
  BTC: '₿',
  ETH: 'Ξ',
  USDT: '₮',
  USDC: '$',
  SOL: '◎',
  BNB: 'B',
}

const tokenColors: Record<string, string> = {
  BTC: 'bg-orange-500',
  ETH: 'bg-purple-500',
  USDT: 'bg-green-500',
  USDC: 'bg-blue-500',
  SOL: 'bg-gradient-to-r from-purple-500 to-cyan-500',
  BNB: 'bg-yellow-500',
}

export const BalanceCard: React.FC<BalanceCardProps> = ({ balance }) => {
  const { currency, available, locked } = balance
  const total = (parseFloat(available) + parseFloat(locked)).toString()
  
  const icon = tokenIcons[currency] || currency.charAt(0)
  const colorClass = tokenColors[currency] || 'bg-accent-blue'

  return (
    <Card hover className="relative overflow-hidden">
      <div className="flex items-start justify-between">
        {/* Token Icon and Name */}
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full ${colorClass} flex items-center justify-center text-white font-bold`}>
            {icon}
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">{currency}</h3>
            <p className="text-sm text-text-tertiary">Balance</p>
          </div>
        </div>
      </div>

      {/* Balance Details */}
      <div className="mt-4 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-secondary">Total</span>
          <span className="font-medium text-text-primary">{formatCrypto(total, currency)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-secondary">Available</span>
          <span className="text-sm text-accent-green">{formatCrypto(available, currency)}</span>
        </div>
        {parseFloat(locked) > 0 && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-text-secondary">Locked</span>
            <span className="text-sm text-accent-yellow">{formatCrypto(locked, currency)}</span>
          </div>
        )}
      </div>
    </Card>
  )
}

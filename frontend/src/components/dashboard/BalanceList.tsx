import React from 'react'
import { BalanceCard } from './BalanceCard'
import { LoadingSpinner } from '../common'
import type { Balance } from '../../types'

interface BalanceListProps {
  balances: Balance[]
  isLoading?: boolean
}

export const BalanceList: React.FC<BalanceListProps> = ({ balances, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    )
  }

  if (balances.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="w-16 h-16 mx-auto text-text-tertiary mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
          />
        </svg>
        <h3 className="text-lg font-medium text-text-primary mb-2">No Balances</h3>
        <p className="text-text-secondary">You don't have any token balances yet.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {balances.map((balance) => (
        <BalanceCard key={balance.currency} balance={balance} />
      ))}
    </div>
  )
}

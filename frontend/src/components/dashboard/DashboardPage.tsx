import React, { useEffect } from 'react'
import { useUser } from '../../hooks'
import { PortfolioSummary } from './PortfolioSummary'
import { BalanceList } from './BalanceList'
import { Card, CardHeader } from '../common'

export const DashboardPage: React.FC = () => {
  const { user, balances, totalValueUsdt, isLoading, refreshData } = useUser()

  useEffect(() => {
    refreshData()
  }, [refreshData])

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Welcome Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          Welcome back{user?.user_name ? `, ${user.user_name}` : ''}
        </h1>
        <p className="text-text-secondary mt-1">
          Here's an overview of your portfolio
        </p>
      </div>

      {/* Portfolio Summary */}
      <PortfolioSummary
        totalValueUsdt={totalValueUsdt}
        balanceCount={balances?.length ?? 0}
        isLoading={isLoading}
      />

      {/* Balances Section */}
      <Card>
        <CardHeader
          title="Your Assets"
          subtitle="View and manage your token balances"
        />
        <BalanceList balances={balances ?? []} isLoading={isLoading} />
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card hover className="cursor-pointer group">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-accent-blue/10 flex items-center justify-center group-hover:bg-accent-blue/20 transition-colors">
              <svg className="w-6 h-6 text-accent-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-text-primary">Swap Tokens</h3>
              <p className="text-sm text-text-secondary">Exchange tokens instantly</p>
            </div>
          </div>
        </Card>

        <Card hover className="cursor-pointer group">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-accent-green/10 flex items-center justify-center group-hover:bg-accent-green/20 transition-colors">
              <svg className="w-6 h-6 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-text-primary">Add Liquidity</h3>
              <p className="text-sm text-text-secondary">Earn fees as a LP</p>
            </div>
          </div>
        </Card>

        <Card hover className="cursor-pointer group">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-accent-yellow/10 flex items-center justify-center group-hover:bg-accent-yellow/20 transition-colors">
              <svg className="w-6 h-6 text-accent-yellow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-text-primary">View History</h3>
              <p className="text-sm text-text-secondary">Check your trade history</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

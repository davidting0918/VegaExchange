import React from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { useUserInitialization } from '../../hooks'

export const MainLayout: React.FC = () => {
  // Initialize user data when layout mounts
  useUserInitialization()

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header */}
      <Header />

      {/* Main Content */}
      <main className="pt-4 pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

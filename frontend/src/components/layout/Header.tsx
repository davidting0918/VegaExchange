import React, { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth, useUser } from '../../hooks'

export const Header: React.FC = () => {
  const location = useLocation()
  const { logout } = useAuth()
  const { user } = useUser()
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isTradeOpen, setIsTradeOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const tradeRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
      if (tradeRef.current && !tradeRef.current.contains(event.target as Node)) {
        setIsTradeOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    await logout()
  }

  const isTradeActive = location.pathname.startsWith('/trade')
  const isPoolsActive = location.pathname.startsWith('/pools')

  return (
    <header className="bg-bg-secondary border-b border-border-default">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and Nav */}
          <div className="flex items-center gap-8">
            {/* Logo */}
            <Link to="/dashboard" className="flex items-center gap-2">
              <svg className="w-8 h-8" viewBox="0 0 100 100">
                <defs>
                  <linearGradient id="headerLogoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{ stopColor: '#58A6FF' }} />
                    <stop offset="100%" style={{ stopColor: '#3FB950' }} />
                  </linearGradient>
                </defs>
                <polygon points="50,10 90,85 10,85" fill="url(#headerLogoGrad)" />
                <text x="50" y="65" fontFamily="Arial, sans-serif" fontSize="24" fontWeight="bold" fill="white" textAnchor="middle">V</text>
              </svg>
              <span className="text-xl font-bold text-text-primary hidden sm:block">Vega</span>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              {/* Dashboard */}
              <Link
                to="/dashboard"
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === '/dashboard'
                    ? 'bg-bg-tertiary text-text-primary'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
                }`}
              >
                Dashboard
              </Link>

              {/* Trade dropdown */}
              <div className="relative" ref={tradeRef}>
                <button
                  onClick={() => setIsTradeOpen(!isTradeOpen)}
                  className={`flex items-center gap-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isTradeActive
                      ? 'bg-bg-tertiary text-text-primary'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
                  }`}
                >
                  Trade
                  <svg
                    className={`w-3 h-3 transition-transform ${isTradeOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isTradeOpen && (
                  <div className="absolute left-0 mt-1 w-40 bg-bg-secondary border border-border-default rounded-lg shadow-card py-1 z-50 animate-fade-in">
                    <Link
                      to="/trade/spot"
                      onClick={() => setIsTradeOpen(false)}
                      className="block px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
                    >
                      Spot
                    </Link>
                    <div className="px-4 py-2 text-sm text-text-tertiary cursor-not-allowed flex items-center justify-between">
                      Perp
                      <span className="text-xs bg-bg-tertiary px-1.5 py-0.5 rounded">Soon</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Pools */}
              <Link
                to="/pools"
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isPoolsActive
                    ? 'bg-bg-tertiary text-text-primary'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
                }`}
              >
                Pools
              </Link>
            </nav>
          </div>

          {/* User Menu */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-bg-tertiary transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center">
                {user?.photo_url ? (
                  <img src={user.photo_url} alt={user.user_name} className="w-8 h-8 rounded-full" />
                ) : (
                  <span className="text-sm font-medium text-accent-blue">
                    {user?.user_name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || 'U'}
                  </span>
                )}
              </div>
              <span className="text-sm text-text-primary hidden sm:block">
                {user?.user_name || user?.email?.split('@')[0] || 'User'}
              </span>
              <svg
                className={`w-4 h-4 text-text-tertiary transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {isDropdownOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-bg-secondary border border-border-default rounded-lg shadow-card py-1 z-50 animate-fade-in">
                <div className="px-4 py-2 border-b border-border-default">
                  <p className="text-sm font-medium text-text-primary truncate">{user?.user_name || 'User'}</p>
                  <p className="text-xs text-text-tertiary truncate">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-left text-sm text-accent-red hover:bg-bg-tertiary transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

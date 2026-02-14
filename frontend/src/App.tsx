import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useDispatch } from 'react-redux'
import { useAuth, useAuthInitialization } from './hooks'
import { wsService } from './api/websocket'
import type { WsMessage } from './api/websocket'
import {
  wsPoolUpdate,
  wsOrderbookUpdate,
  wsPoolUserUpdate,
} from './store/slices/tradingSlice'
import { wsUserUpdate } from './store/slices/userSlice'
import { MainLayout } from './components/layout/MainLayout'
import { LoginPage } from './components/auth/LoginPage'
import { RegisterPage } from './components/auth/RegisterPage'
import { DashboardPage } from './components/dashboard/DashboardPage'
import { TradingPage } from './components/trading/TradingPage'
import { PoolDetailPage } from './components/pool/PoolDetailPage'
import { MarketPage } from './components/market/MarketPage'
import { LoadingSpinner } from './components/common/LoadingSpinner'

// Protected route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg-primary">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Public route wrapper (redirects to dashboard if authenticated)
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg-primary">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

function WebSocketManager() {
  const dispatch = useDispatch()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    const token = localStorage.getItem('vega_access_token')
    wsService.setToken(token)
    wsService.setMessageHandler((msg: WsMessage) => {
      if (msg.channel === 'pool' && msg.data && typeof msg.data === 'object') {
        dispatch(wsPoolUpdate(msg.data as Record<string, unknown>))
      } else if (msg.channel === 'user' && msg.data && typeof msg.data === 'object') {
        const d = msg.data as { balances?: unknown[]; pool_user?: Record<string, unknown> }
        if (Array.isArray(d.balances)) {
          dispatch(
            wsUserUpdate({
              balances: d.balances as Array<{ currency: string; available: number; locked: number; total?: number }>,
            })
          )
        }
        if (d.pool_user) {
          dispatch(wsPoolUserUpdate(d.pool_user))
        }
      } else if (msg.channel === 'orderbook' && msg.symbol && msg.data && typeof msg.data === 'object') {
        const d = msg.data as { bids?: Array<{ price: string | number; quantity: string | number }>; asks?: Array<{ price: string | number; quantity: string | number }> }
        const mapLevel = (l: { price: string | number; quantity: string | number }) => ({
          price: String(l.price),
          quantity: String(l.quantity),
        })
        dispatch(
          wsOrderbookUpdate({
            symbol: msg.symbol,
            bids: (d.bids || []).map(mapLevel),
            asks: (d.asks || []).map(mapLevel),
          })
        )
      }
    })
    wsService.connect()
    return () => wsService.disconnect()
  }, [dispatch])

  useEffect(() => {
    const token = isAuthenticated ? localStorage.getItem('vega_access_token') : null
    wsService.setToken(token)
    if (wsService.isConnected()) {
      wsService.disconnect()
      wsService.connect()
    }
  }, [isAuthenticated])

  return null
}

function App() {
  // Initialize auth state on app load
  useAuthInitialization()

  return (
    <>
      <WebSocketManager />
    <Routes>
      {/* Public Routes */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />

      {/* Protected Routes */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="trade" element={<TradingPage />} />
        <Route path="trade/:marketId" element={<TradingPage />} />
        <Route path="pools/:symbolPath" element={<PoolDetailPage />} />
        <Route path="market/:base/:quote/:settle/:market" element={<MarketPage />} />
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
    </>
  )
}

export default App

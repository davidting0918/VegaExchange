import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth, useAuthInitialization } from './hooks'
import { MainLayout } from './components/layout/MainLayout'
import { LoginPage } from './components/auth/LoginPage'
import { RegisterPage } from './components/auth/RegisterPage'
import { DashboardPage } from './components/dashboard/DashboardPage'
import { TradingPage } from './components/trading/TradingPage'
import { MarketPage } from './components/market/MarketPage'
import { PoolsListPage } from './components/pool/PoolsListPage'
import { PoolDetailPage } from './components/pool/PoolDetailPage'
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

function App() {
  useAuthInitialization()

  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

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

        {/* Trade section (CLOB order book) */}
        <Route path="trade" element={<Navigate to="/trade/spot" replace />} />
        <Route path="trade/spot" element={<TradingPage />} />
        <Route path="trade/spot/:pair" element={<MarketPage />} />

        {/* Pools section (AMM) */}
        <Route path="pools" element={<PoolsListPage />} />
        <Route path="pools/:pair" element={<PoolDetailPage />} />

        {/* Legacy redirects */}
        <Route path="market/:base/:quote/:settle/:market" element={<Navigate to="/trade/spot" replace />} />
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App

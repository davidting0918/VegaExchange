import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { AuthService } from '@/api/services/AuthService'
import { STORAGE_KEYS, clearTokens } from '@/api/client'
import type { Admin } from '@/types/admin'

interface AuthState {
  admin: Admin | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (idToken: string) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Check stored tokens on mount
  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEYS.accessToken)
    const storedAdmin = localStorage.getItem('vega_admin_profile')
    if (token && storedAdmin) {
      try {
        setAdmin(JSON.parse(storedAdmin))
      } catch {
        clearTokens()
        localStorage.removeItem('vega_admin_profile')
      }
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (idToken: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await AuthService.adminGoogleAuth(idToken)
      if (response.success && response.data) {
        const { admin: adminData, access_token, refresh_token } = response.data
        localStorage.setItem(STORAGE_KEYS.accessToken, access_token)
        localStorage.setItem(STORAGE_KEYS.refreshToken, refresh_token)
        localStorage.setItem(STORAGE_KEYS.adminId, adminData.admin_id)
        localStorage.setItem('vega_admin_profile', JSON.stringify(adminData))
        setAdmin(adminData)
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosErr.response?.status === 403) {
        setError('Access denied. Your email is not on the admin whitelist.')
      } else {
        setError(axiosErr.response?.data?.detail || 'Login failed. Please try again.')
      }
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await AuthService.logout()
    } catch {
      // Continue with local cleanup even if API call fails
    }
    clearTokens()
    localStorage.removeItem('vega_admin_profile')
    setAdmin(null)
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return (
    <AuthContext.Provider
      value={{
        admin,
        isAuthenticated: !!admin,
        isLoading,
        error,
        login,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

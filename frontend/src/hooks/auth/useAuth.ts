import { useCallback, useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../redux'
import {
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  initializeAuth,
  clearError,
} from '../../store'
import type { EmailLoginRequest } from '../../types'

export const useAuth = () => {
  const dispatch = useAppDispatch()
  const authState = useAppSelector((state) => state.auth)

  const login = useCallback(
    async (request: EmailLoginRequest) => {
      const result = await dispatch(loginWithEmail(request))
      if (loginWithEmail.rejected.match(result)) {
        throw new Error(result.payload as string)
      }
    },
    [dispatch]
  )

  const googleLogin = useCallback(
    async (googleId: string) => {
      const result = await dispatch(loginWithGoogle(googleId))
      if (loginWithGoogle.rejected.match(result)) {
        throw new Error(result.payload as string)
      }
    },
    [dispatch]
  )

  const logout = useCallback(async () => {
    await dispatch(logoutUser())
  }, [dispatch])

  const clearAuthError = useCallback(() => {
    dispatch(clearError())
  }, [dispatch])

  return {
    isAuthenticated: authState.isAuthenticated,
    isLoading: authState.isLoading,
    error: authState.error,
    login,
    googleLogin,
    logout,
    clearAuthError,
  }
}

export const useAuthInitialization = () => {
  const dispatch = useAppDispatch()
  const { isAuthenticated, isLoading } = useAppSelector((state) => state.auth)

  useEffect(() => {
    // Only initialize if we haven't checked yet
    const accessToken = localStorage.getItem('vega_access_token')
    if (accessToken && !isAuthenticated && isLoading) {
      dispatch(initializeAuth())
    } else if (!accessToken && isLoading) {
      // No token, stop loading
      dispatch(initializeAuth())
    }
  }, [dispatch, isAuthenticated, isLoading])

  // Listen for logout events from API client
  useEffect(() => {
    const handleLogout = () => {
      dispatch(logoutUser())
    }

    window.addEventListener('auth:logout', handleLogout)
    return () => {
      window.removeEventListener('auth:logout', handleLogout)
    }
  }, [dispatch])
}

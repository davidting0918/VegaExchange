import { useCallback, useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../redux'
import {
  fetchCurrentUser,
  fetchBalances,
  fetchPortfolio,
  clearUserError,
} from '../../store'

export const useUser = () => {
  const dispatch = useAppDispatch()
  const userState = useAppSelector((state) => state.user)
  const { isAuthenticated } = useAppSelector((state) => state.auth)

  const loadUser = useCallback(async () => {
    if (!isAuthenticated) return
    const result = await dispatch(fetchCurrentUser())
    if (fetchCurrentUser.rejected.match(result)) {
      throw new Error(result.payload as string)
    }
  }, [dispatch, isAuthenticated])

  const loadBalances = useCallback(async () => {
    if (!isAuthenticated) return
    const result = await dispatch(fetchBalances())
    if (fetchBalances.rejected.match(result)) {
      throw new Error(result.payload as string)
    }
  }, [dispatch, isAuthenticated])

  const loadPortfolio = useCallback(async () => {
    if (!isAuthenticated) return
    const result = await dispatch(fetchPortfolio())
    if (fetchPortfolio.rejected.match(result)) {
      throw new Error(result.payload as string)
    }
  }, [dispatch, isAuthenticated])

  const refreshData = useCallback(async () => {
    if (!isAuthenticated) return
    await Promise.all([loadUser(), loadBalances(), loadPortfolio()])
  }, [isAuthenticated, loadUser, loadBalances, loadPortfolio])

  const clearError = useCallback(() => {
    dispatch(clearUserError())
  }, [dispatch])

  return {
    user: userState.user,
    balances: userState.balances,
    portfolio: userState.portfolio,
    totalValueUsdt: userState.totalValueUsdt,
    isLoading: userState.isLoading,
    error: userState.error,
    loadUser,
    loadBalances,
    loadPortfolio,
    refreshData,
    clearError,
  }
}

export const useUserInitialization = () => {
  const dispatch = useAppDispatch()
  const { user, isLoading } = useAppSelector((state) => state.user)
  const { isAuthenticated, isLoading: authLoading } = useAppSelector((state) => state.auth)

  useEffect(() => {
    // Load user data when authenticated and not already loaded
    if (isAuthenticated && !authLoading && !user && !isLoading) {
      dispatch(fetchCurrentUser())
      dispatch(fetchBalances())
      dispatch(fetchPortfolio())
    }
  }, [dispatch, isAuthenticated, authLoading, user, isLoading])
}

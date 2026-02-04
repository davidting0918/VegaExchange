import { useCallback, useEffect, useRef } from 'react'
import { useAppDispatch, useAppSelector } from '../redux'
import {
  fetchSymbols,
  fetchPoolInfo,
  fetchLPPosition,
  fetchQuote,
  fetchRecentTrades,
  setCurrentSymbol,
  clearQuote,
  clearTradingError,
} from '../../store'
import { tradeService } from '../../api'
import type { QuoteRequest, SwapRequest, AddLiquidityRequest, RemoveLiquidityRequest } from '../../types'

export const useTrading = () => {
  const dispatch = useAppDispatch()
  const tradingState = useAppSelector((state) => state.trading)
  const { isAuthenticated } = useAppSelector((state) => state.auth)

  const loadSymbols = useCallback(async () => {
    const result = await dispatch(fetchSymbols())
    if (fetchSymbols.rejected.match(result)) {
      throw new Error(result.payload as string)
    }
    return result.payload
  }, [dispatch])

  const selectSymbol = useCallback(
    async (symbol: string) => {
      dispatch(setCurrentSymbol(symbol))
      // Load pool info and recent trades
      await Promise.all([
        dispatch(fetchPoolInfo(symbol)),
        dispatch(fetchRecentTrades(symbol)),
        isAuthenticated ? dispatch(fetchLPPosition(symbol)) : Promise.resolve(),
      ])
    },
    [dispatch, isAuthenticated]
  )

  const refreshPoolData = useCallback(async () => {
    if (!tradingState.currentSymbol) return
    await Promise.all([
      dispatch(fetchPoolInfo(tradingState.currentSymbol)),
      dispatch(fetchRecentTrades(tradingState.currentSymbol)),
      isAuthenticated ? dispatch(fetchLPPosition(tradingState.currentSymbol)) : Promise.resolve(),
    ])
  }, [dispatch, tradingState.currentSymbol, isAuthenticated])

  const getQuote = useCallback(
    async (request: QuoteRequest) => {
      const result = await dispatch(fetchQuote(request))
      if (fetchQuote.rejected.match(result)) {
        throw new Error(result.payload as string)
      }
      return result.payload
    },
    [dispatch]
  )

  const executeSwap = useCallback(
    async (request: SwapRequest) => {
      const response = await tradeService.swap(request)
      if (!response.success) {
        throw new Error(response.message || 'Swap failed')
      }
      // Refresh pool data after swap
      await refreshPoolData()
      return response.data
    },
    [refreshPoolData]
  )

  const addLiquidity = useCallback(
    async (request: AddLiquidityRequest) => {
      const response = await tradeService.addLiquidity(request)
      if (!response.success) {
        throw new Error(response.message || 'Add liquidity failed')
      }
      // Refresh pool data after adding liquidity
      await refreshPoolData()
      return response.data
    },
    [refreshPoolData]
  )

  const removeLiquidity = useCallback(
    async (request: RemoveLiquidityRequest) => {
      const response = await tradeService.removeLiquidity(request)
      if (!response.success) {
        throw new Error(response.message || 'Remove liquidity failed')
      }
      // Refresh pool data after removing liquidity
      await refreshPoolData()
      return response.data
    },
    [refreshPoolData]
  )

  const clearCurrentQuote = useCallback(() => {
    dispatch(clearQuote())
  }, [dispatch])

  const clearError = useCallback(() => {
    dispatch(clearTradingError())
  }, [dispatch])

  return {
    symbols: tradingState.symbols,
    currentSymbol: tradingState.currentSymbol,
    poolInfo: tradingState.poolInfo,
    lpPosition: tradingState.lpPosition,
    quote: tradingState.quote,
    recentTrades: tradingState.recentTrades,
    isLoading: tradingState.isLoading,
    isQuoteLoading: tradingState.isQuoteLoading,
    error: tradingState.error,
    loadSymbols,
    selectSymbol,
    refreshPoolData,
    getQuote,
    executeSwap,
    addLiquidity,
    removeLiquidity,
    clearQuote: clearCurrentQuote,
    clearError,
  }
}

export const useTradingInitialization = () => {
  const dispatch = useAppDispatch()
  const { symbols, isLoading } = useAppSelector((state) => state.trading)
  const initialized = useRef(false)

  useEffect(() => {
    // Load symbols on mount if not already loaded
    if (!initialized.current && symbols.length === 0 && !isLoading) {
      initialized.current = true
      dispatch(fetchSymbols())
    }
  }, [dispatch, symbols.length, isLoading])
}

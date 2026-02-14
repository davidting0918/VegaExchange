import { configureStore } from '@reduxjs/toolkit'
import authReducer from './slices/authSlice'
import userReducer from './slices/userSlice'
import tradingReducer from './slices/tradingSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    user: userReducer,
    trading: tradingReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [],
      },
    }),
  devTools: import.meta.env.DEV,
})

// Export types for typed hooks
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

// Re-export actions from slices
export {
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  initializeAuth,
  clearError,
  logout,
} from './slices/authSlice'

export {
  fetchCurrentUser,
  fetchBalances,
  fetchPortfolio,
  clearUserError,
  clearUserState,
  wsUserUpdate,
} from './slices/userSlice'

export {
  fetchSymbols,
  fetchPoolInfo,
  fetchLPPosition,
  fetchQuote,
  fetchRecentTrades,
  fetchPoolPublic,
  fetchPoolUser,
  setCurrentSymbol,
  clearQuote,
  clearTradingError,
  clearTradingState,
  wsPoolUpdate,
  wsOrderbookUpdate,
  wsPoolUserUpdate,
  setOrderbookSnapshot,
} from './slices/tradingSlice'

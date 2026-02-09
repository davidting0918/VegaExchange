import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { TradingState, Symbol, PoolInfo, LPPosition, QuoteResponse, Trade, QuoteRequest } from '../../types'
import { marketService, tradeService } from '../../api'
import { logout, logoutUser } from './authSlice'

const initialState: TradingState = {
  symbols: [],
  currentSymbol: null,
  poolInfo: null,
  lpPosition: null,
  quote: null,
  recentTrades: [],
  poolBaseBalance: null,
  poolQuoteBalance: null,
  isLoading: false,
  isQuoteLoading: false,
  error: null,
}

// Fetch all symbols
export const fetchSymbols = createAsyncThunk<Symbol[], void, { rejectValue: string }>(
  'trading/fetchSymbols',
  async (_, { rejectWithValue }) => {
    try {
      const response = await marketService.getSymbols()
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch symbols')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch symbols'
      return rejectWithValue(message)
    }
  }
)

// Fetch pool info for a symbol
export const fetchPoolInfo = createAsyncThunk<PoolInfo, string, { rejectValue: string }>(
  'trading/fetchPoolInfo',
  async (symbol, { rejectWithValue }) => {
    try {
      const response = await marketService.getPoolData(symbol)
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch pool info')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch pool info'
      return rejectWithValue(message)
    }
  }
)

// Fetch LP position
export const fetchLPPosition = createAsyncThunk<LPPosition | null, string, { rejectValue: string }>(
  'trading/fetchLPPosition',
  async (symbol) => {
    try {
      const response = await tradeService.getLPPosition(symbol)
      if (response.success && response.data) {
        return response.data
      }
      return null
    } catch {
      // LP position might not exist, return null instead of error
      console.log('No LP position found')
      return null
    }
  }
)

// Fetch quote
export const fetchQuote = createAsyncThunk<QuoteResponse, QuoteRequest, { rejectValue: string }>(
  'trading/fetchQuote',
  async (request, { rejectWithValue }) => {
    try {
      const response = await tradeService.getQuote(request)
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch quote')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch quote'
      return rejectWithValue(message)
    }
  }
)

// Fetch recent trades for a symbol
// Parameters: { symbol: string, engineType?: number, limit?: number }
export const fetchRecentTrades = createAsyncThunk<
  Trade[],
  { symbol: string; engineType?: number; limit?: number },
  { rejectValue: string }
>(
  'trading/fetchRecentTrades',
  async ({ symbol, engineType = 0, limit = 100 }, { rejectWithValue }) => {
    try {
      // engineType: 0 = AMM, 1 = CLOB
      const response = await marketService.getRecentTrades(symbol, engineType, limit)
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch recent trades')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch recent trades'
      return rejectWithValue(message)
    }
  }
)

// Fetch public pool data + trades in one call (reduces API calls)
export const fetchPoolPublic = createAsyncThunk<
  { poolInfo: PoolInfo; trades: Trade[] },
  string,
  { rejectValue: string }
>(
  'trading/fetchPoolPublic',
  async (symbol, { rejectWithValue }) => {
    try {
      const response = await marketService.getPoolPublic(symbol)
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch pool public data')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch pool public data'
      return rejectWithValue(message)
    }
  }
)

// Fetch user-specific pool data (LP position + balances). Requires auth.
export const fetchPoolUser = createAsyncThunk<
  { lpPosition: LPPosition | null; baseBalance: string; quoteBalance: string },
  string,
  { rejectValue: string }
>(
  'trading/fetchPoolUser',
  async (symbol, { rejectWithValue }) => {
    try {
      const response = await marketService.getPoolUser(symbol)
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch pool user data')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch pool user data'
      return rejectWithValue(message)
    }
  }
)

const tradingSlice = createSlice({
  name: 'trading',
  initialState,
  reducers: {
    setCurrentSymbol: (state, action: PayloadAction<string>) => {
      state.currentSymbol = action.payload
      state.quote = null
      state.lpPosition = null
      state.poolBaseBalance = null
      state.poolQuoteBalance = null
    },
    clearQuote: (state) => {
      state.quote = null
    },
    clearTradingError: (state) => {
      state.error = null
    },
    clearTradingState: (state) => {
      state.symbols = []
      state.currentSymbol = null
      state.poolInfo = null
      state.lpPosition = null
      state.quote = null
      state.recentTrades = []
      state.poolBaseBalance = null
      state.poolQuoteBalance = null
      state.isLoading = false
      state.isQuoteLoading = false
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch symbols
      .addCase(fetchSymbols.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchSymbols.fulfilled, (state, action) => {
        state.isLoading = false
        state.symbols = action.payload
      })
      .addCase(fetchSymbols.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch symbols'
      })

      // Fetch pool info
      .addCase(fetchPoolInfo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchPoolInfo.fulfilled, (state, action) => {
        state.isLoading = false
        state.poolInfo = action.payload
      })
      .addCase(fetchPoolInfo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch pool info'
      })

      // Fetch LP position
      .addCase(fetchLPPosition.fulfilled, (state, action) => {
        state.lpPosition = action.payload
      })

      // Fetch quote
      .addCase(fetchQuote.pending, (state) => {
        state.isQuoteLoading = true
      })
      .addCase(fetchQuote.fulfilled, (state, action) => {
        state.isQuoteLoading = false
        state.quote = action.payload
      })
      .addCase(fetchQuote.rejected, (state, action) => {
        state.isQuoteLoading = false
        state.error = action.payload || 'Failed to fetch quote'
      })

      // Fetch recent trades
      .addCase(fetchRecentTrades.fulfilled, (state, action) => {
        state.recentTrades = action.payload
      })

      // Fetch pool public (pool info + trades)
      .addCase(fetchPoolPublic.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchPoolPublic.fulfilled, (state, action) => {
        state.isLoading = false
        state.poolInfo = action.payload.poolInfo
        state.recentTrades = action.payload.trades
      })
      .addCase(fetchPoolPublic.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch pool public data'
      })

      // Fetch pool user (LP position + balances)
      .addCase(fetchPoolUser.fulfilled, (state, action) => {
        state.lpPosition = action.payload.lpPosition
        state.poolBaseBalance = action.payload.baseBalance
        state.poolQuoteBalance = action.payload.quoteBalance
      })

      // Handle logout - clear trading state
      .addCase(logout, (state) => {
        state.lpPosition = null
        state.quote = null
        state.poolBaseBalance = null
        state.poolQuoteBalance = null
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.lpPosition = null
        state.quote = null
        state.poolBaseBalance = null
        state.poolQuoteBalance = null
      })
  },
})

export const { setCurrentSymbol, clearQuote, clearTradingError, clearTradingState } = tradingSlice.actions
export default tradingSlice.reducer

import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { UserState, User, Balance, PortfolioItem } from '../../types'
import { userService } from '../../api'
import { logout, logoutUser } from './authSlice'

const initialState: UserState = {
  user: null,
  balances: [],
  portfolio: [],
  totalValueUsdt: '0',
  isLoading: false,
  error: null,
}

// Fetch current user
export const fetchCurrentUser = createAsyncThunk<User, void, { rejectValue: string }>(
  'user/fetchCurrentUser',
  async (_, { rejectWithValue }) => {
    try {
      const response = await userService.getCurrentUser()
      if (response.success && response.data) {
        return response.data
      }
      throw new Error(response.message || 'Failed to fetch user')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch user'
      return rejectWithValue(message)
    }
  }
)

// Fetch balances
export const fetchBalances = createAsyncThunk<Balance[], void, { rejectValue: string }>(
  'user/fetchBalances',
  async (_, { rejectWithValue }) => {
    try {
      const response = await userService.getBalances()
      if (response.success && response.data) {
        // Backend returns array directly, or { balances: [...] } format
        const data = response.data
        const balances = Array.isArray(data) ? data : (data.balances || [])
        
        // Transform backend format to frontend Balance type
        return balances.map((b: { currency: string; available: number | string; locked: number | string; total?: number | string }) => ({
          currency: b.currency,
          available: String(b.available),
          balance: String(b.total ?? b.available),
          locked: String(b.locked),
        }))
      }
      throw new Error(response.message || 'Failed to fetch balances')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to fetch balances'
      return rejectWithValue(message)
    }
  }
)

// Fetch portfolio
export const fetchPortfolio = createAsyncThunk<
  { items: PortfolioItem[]; totalValueUsdt: string },
  void,
  { rejectValue: string }
>('user/fetchPortfolio', async (_, { rejectWithValue }) => {
  try {
    const response = await userService.getPortfolio()
    if (response.success && response.data) {
      return {
        items: response.data.items,
        totalValueUsdt: response.data.total_value_usdt,
      }
    }
    throw new Error(response.message || 'Failed to fetch portfolio')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to fetch portfolio'
    return rejectWithValue(message)
  }
})

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    clearUserError: (state) => {
      state.error = null
    },
    clearUserState: (state) => {
      state.user = null
      state.balances = []
      state.portfolio = []
      state.totalValueUsdt = '0'
      state.isLoading = false
      state.error = null
    },
    // WebSocket: user balances (and optionally pool_user is handled in trading slice)
    wsUserUpdate: (state, action: PayloadAction<{ balances: Array<{ currency: string; available: number; locked: number; total?: number }> }>) => {
      const { balances } = action.payload
      if (!Array.isArray(balances)) return
      state.balances = balances.map((b) => ({
        currency: b.currency,
        available: String(b.available),
        balance: String(b.total ?? b.available),
        locked: String(b.locked),
      }))
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch current user
      .addCase(fetchCurrentUser.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.isLoading = false
        state.user = action.payload
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch user'
      })

      // Fetch balances
      .addCase(fetchBalances.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchBalances.fulfilled, (state, action) => {
        state.isLoading = false
        state.balances = action.payload
      })
      .addCase(fetchBalances.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch balances'
      })

      // Fetch portfolio
      .addCase(fetchPortfolio.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchPortfolio.fulfilled, (state, action) => {
        state.isLoading = false
        state.portfolio = action.payload.items
        state.totalValueUsdt = action.payload.totalValueUsdt
      })
      .addCase(fetchPortfolio.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Failed to fetch portfolio'
      })

      // Handle logout - clear user state
      .addCase(logout, (state) => {
        state.user = null
        state.balances = []
        state.portfolio = []
        state.totalValueUsdt = '0'
        state.isLoading = false
        state.error = null
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.user = null
        state.balances = []
        state.portfolio = []
        state.totalValueUsdt = '0'
        state.isLoading = false
        state.error = null
      })
  },
})

export const { clearUserError, clearUserState, wsUserUpdate } = userSlice.actions
export default userSlice.reducer

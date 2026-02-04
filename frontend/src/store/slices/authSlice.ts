import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { AuthState, EmailLoginRequest, TokenResponse } from '../../types'
import { authService } from '../../api'

const initialState: AuthState = {
  isAuthenticated: false,
  isLoading: true, // Start with loading to check stored tokens
  accessToken: localStorage.getItem('vega_access_token'),
  refreshToken: localStorage.getItem('vega_refresh_token'),
  error: null,
}

// Email login thunk
export const loginWithEmail = createAsyncThunk<
  TokenResponse,
  EmailLoginRequest,
  { rejectValue: string }
>('auth/loginWithEmail', async (request, { rejectWithValue }) => {
  try {
    const response = await authService.loginWithEmail(request)
    if (response.success && response.data) {
      return response.data
    }
    throw new Error(response.message || 'Login failed')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Login failed'
    return rejectWithValue(message)
  }
})

// Google login thunk
export const loginWithGoogle = createAsyncThunk<
  TokenResponse,
  string, // google_id
  { rejectValue: string }
>('auth/loginWithGoogle', async (googleId, { rejectWithValue }) => {
  try {
    const response = await authService.loginWithGoogle(googleId)
    if (response.success && response.data) {
      return response.data
    }
    throw new Error(response.message || 'Google login failed')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Google login failed'
    return rejectWithValue(message)
  }
})

// Logout thunk
export const logoutUser = createAsyncThunk<void, void, { rejectValue: string }>(
  'auth/logout',
  async (_, { rejectWithValue }) => {
    try {
      await authService.logout()
    } catch (error: unknown) {
      // Still proceed with logout even if API call fails
      console.error('Logout API error:', error)
      return rejectWithValue('Logout failed')
    }
  }
)

// Initialize auth state from stored tokens
export const initializeAuth = createAsyncThunk<boolean, void, { rejectValue: string }>(
  'auth/initialize',
  async (_, { rejectWithValue }) => {
    const accessToken = localStorage.getItem('vega_access_token')
    const refreshToken = localStorage.getItem('vega_refresh_token')

    if (!accessToken || !refreshToken) {
      return false
    }

    // Try to refresh the token to verify it's still valid
    try {
      const response = await authService.refreshToken({ refresh_token: refreshToken })
      if (response.success && response.data) {
        localStorage.setItem('vega_access_token', response.data.access_token)
        localStorage.setItem('vega_refresh_token', response.data.refresh_token)
        return true
      }
      return false
    } catch {
      // Token is invalid, clear storage
      localStorage.removeItem('vega_access_token')
      localStorage.removeItem('vega_refresh_token')
      return rejectWithValue('Session expired')
    }
  }
)

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null
    },
    logout: (state) => {
      state.isAuthenticated = false
      state.accessToken = null
      state.refreshToken = null
      state.error = null
      localStorage.removeItem('vega_access_token')
      localStorage.removeItem('vega_refresh_token')
      localStorage.removeItem('vega_user_id')
    },
  },
  extraReducers: (builder) => {
    builder
      // Initialize auth
      .addCase(initializeAuth.pending, (state) => {
        state.isLoading = true
      })
      .addCase(initializeAuth.fulfilled, (state, action) => {
        state.isLoading = false
        state.isAuthenticated = action.payload
        if (action.payload) {
          state.accessToken = localStorage.getItem('vega_access_token')
          state.refreshToken = localStorage.getItem('vega_refresh_token')
        }
      })
      .addCase(initializeAuth.rejected, (state) => {
        state.isLoading = false
        state.isAuthenticated = false
        state.accessToken = null
        state.refreshToken = null
      })

      // Email login
      .addCase(loginWithEmail.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(loginWithEmail.fulfilled, (state, action) => {
        state.isLoading = false
        state.isAuthenticated = true
        state.accessToken = action.payload.access_token
        state.refreshToken = action.payload.refresh_token
        localStorage.setItem('vega_access_token', action.payload.access_token)
        localStorage.setItem('vega_refresh_token', action.payload.refresh_token)
      })
      .addCase(loginWithEmail.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Login failed'
      })

      // Google login
      .addCase(loginWithGoogle.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(loginWithGoogle.fulfilled, (state, action) => {
        state.isLoading = false
        state.isAuthenticated = true
        state.accessToken = action.payload.access_token
        state.refreshToken = action.payload.refresh_token
        localStorage.setItem('vega_access_token', action.payload.access_token)
        localStorage.setItem('vega_refresh_token', action.payload.refresh_token)
      })
      .addCase(loginWithGoogle.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Google login failed'
      })

      // Logout
      .addCase(logoutUser.fulfilled, (state) => {
        state.isAuthenticated = false
        state.accessToken = null
        state.refreshToken = null
        localStorage.removeItem('vega_access_token')
        localStorage.removeItem('vega_refresh_token')
        localStorage.removeItem('vega_user_id')
      })
      .addCase(logoutUser.rejected, (state) => {
        // Still logout on client side
        state.isAuthenticated = false
        state.accessToken = null
        state.refreshToken = null
        localStorage.removeItem('vega_access_token')
        localStorage.removeItem('vega_refresh_token')
        localStorage.removeItem('vega_user_id')
      })
  },
})

export const { clearError, logout } = authSlice.actions
export default authSlice.reducer

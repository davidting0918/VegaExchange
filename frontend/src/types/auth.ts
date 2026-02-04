// Login request types
export interface EmailLoginRequest {
  email: string
  password: string
}

export interface GoogleLoginRequest {
  google_id: string
}

// Register request types
export interface EmailRegisterRequest {
  email: string
  password: string
  user_name?: string
}

// Token response
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// Refresh token request
export interface RefreshTokenRequest {
  refresh_token: string
}

// Auth state
export interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  accessToken: string | null
  refreshToken: string | null
  error: string | null
}

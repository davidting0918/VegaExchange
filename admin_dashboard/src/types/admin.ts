export interface Admin {
  admin_id: string
  email: string
  name: string
  photo_url?: string
  role: string
  is_active: boolean
}

export interface AdminAuthResponse {
  admin: Admin
  is_new_admin: boolean
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface TokenRefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface APIResponse<T = unknown> {
  success: boolean
  data?: T
  error?: { message: string; code?: string }
}

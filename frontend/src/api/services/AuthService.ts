import { apiClient } from '../client'
import type {
  ApiResponse,
  EmailLoginRequest,
  EmailRegisterRequest,
  TokenResponse,
  RefreshTokenRequest,
} from '../../types'

class AuthService {
  private basePath = '/api/auth'

  // Email login
  async loginWithEmail(request: EmailLoginRequest): Promise<ApiResponse<TokenResponse>> {
    const response = await apiClient.post(`${this.basePath}/login/email`, request)
    return response.data
  }

  // Unified Google auth (login or register)
  // Send the Google ID token, backend handles login or registration automatically
  async authWithGoogle(idToken: string): Promise<ApiResponse<TokenResponse & { is_new_user: boolean }>> {
    const response = await apiClient.post(`${this.basePath}/google`, {
      id_token: idToken,
    })
    return response.data
  }

  // [DEPRECATED] Use authWithGoogle instead
  async loginWithGoogle(googleId: string): Promise<ApiResponse<TokenResponse>> {
    const response = await apiClient.post(`${this.basePath}/login`, null, {
      params: { google_id: googleId },
    })
    return response.data
  }

  // Email registration
  async registerWithEmail(
    request: EmailRegisterRequest,
    apiKey: string,
    apiSecret: string
  ): Promise<ApiResponse<TokenResponse>> {
    const response = await apiClient.post(`${this.basePath}/register/email`, request, {
      headers: {
        'X-API-Key': apiKey,
        'X-API-Secret': apiSecret,
      },
    })
    return response.data
  }

  // [DEPRECATED] Use authWithGoogle instead
  async registerWithGoogle(
    googleId: string,
    email: string,
    userName: string,
    photoUrl: string | undefined,
    apiKey: string,
    apiSecret: string
  ): Promise<ApiResponse<TokenResponse>> {
    const response = await apiClient.post(
      `${this.basePath}/register`,
      {
        google_id: googleId,
        email,
        user_name: userName,
        photo_url: photoUrl,
      },
      {
        headers: {
          'X-API-Key': apiKey,
          'X-API-Secret': apiSecret,
        },
      }
    )
    return response.data
  }

  // Refresh token
  async refreshToken(request: RefreshTokenRequest): Promise<ApiResponse<TokenResponse>> {
    // Backend expects refresh_token as query parameter
    const response = await apiClient.post(
      `${this.basePath}/refresh?refresh_token=${encodeURIComponent(request.refresh_token)}`
    )
    return response.data
  }

  // Logout
  async logout(): Promise<ApiResponse<null>> {
    const response = await apiClient.post(`${this.basePath}/logout`)
    return response.data
  }
}

export const authService = new AuthService()

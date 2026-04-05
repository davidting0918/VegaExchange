import client from '@/api/client'
import type { AdminAuthResponse, APIResponse } from '@/types/admin'

export const AuthService = {
  async adminGoogleAuth(idToken: string): Promise<APIResponse<AdminAuthResponse>> {
    const res = await client.post('/api/auth/admin/google', { id_token: idToken })
    return res.data
  },

  async logout(): Promise<APIResponse> {
    const res = await client.post('/api/auth/admin/logout')
    return res.data
  },
}

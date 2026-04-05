import axios from 'axios'
import type { TokenRefreshResponse, APIResponse } from '@/types/admin'

const STORAGE_KEYS = {
  accessToken: 'vega_admin_access_token',
  refreshToken: 'vega_admin_refresh_token',
  adminId: 'vega_admin_id',
} as const

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach Bearer token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.accessToken)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: auto-refresh on 401
let refreshPromise: Promise<string> | null = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    original._retry = true
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken)
    if (!refreshToken) {
      clearTokens()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // Share a single refresh promise to avoid concurrent refresh calls
    if (!refreshPromise) {
      refreshPromise = doRefresh(refreshToken)
    }

    try {
      const newAccessToken = await refreshPromise
      original.headers.Authorization = `Bearer ${newAccessToken}`
      return client(original)
    } catch {
      clearTokens()
      window.location.href = '/login'
      return Promise.reject(error)
    } finally {
      refreshPromise = null
    }
  }
)

async function doRefresh(refreshToken: string): Promise<string> {
  // Use fetch to avoid interceptor recursion
  const res = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/auth/admin/refresh?refresh_token=${encodeURIComponent(refreshToken)}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error('Refresh failed')
  const json: APIResponse<TokenRefreshResponse> = await res.json()
  if (!json.success || !json.data) throw new Error('Refresh failed')

  localStorage.setItem(STORAGE_KEYS.accessToken, json.data.access_token)
  localStorage.setItem(STORAGE_KEYS.refreshToken, json.data.refresh_token)
  return json.data.access_token
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEYS.accessToken)
  localStorage.removeItem(STORAGE_KEYS.refreshToken)
  localStorage.removeItem(STORAGE_KEYS.adminId)
}

export { STORAGE_KEYS }
export default client

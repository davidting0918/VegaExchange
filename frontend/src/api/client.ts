import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'

// Extended config type to track retry attempts
interface ExtendedAxiosRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

class ApiClient {
  private client: AxiosInstance
  private isRefreshing = false
  private refreshSubscribers: Array<(token: string) => void> = []

  constructor() {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  // Subscribe to token refresh - called by requests waiting for refresh
  private subscribeTokenRefresh(callback: (token: string) => void) {
    this.refreshSubscribers.push(callback)
  }

  // Notify all subscribers with new token
  private onTokenRefreshed(token: string) {
    this.refreshSubscribers.forEach((callback) => callback(token))
    this.refreshSubscribers = []
  }

  // Notify all subscribers that refresh failed
  private onRefreshFailed() {
    this.refreshSubscribers = []
  }

  private logApiError(error: AxiosError) {
    if (!error.response) return
    console.error('[API Error]', {
      method: error.config?.method?.toUpperCase(),
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      status: error.response?.status,
      data: error.response?.data,
    })
  }

  private setupInterceptors() {
    // Request interceptor - add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('vega_access_token')
        if (token && !config.headers.Authorization) {
          config.headers.Authorization = `Bearer ${token}`
        }

        // Handle FormData (for file uploads)
        if (config.data instanceof FormData) {
          delete config.headers['Content-Type']
        }

        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor - handle errors
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as ExtendedAxiosRequestConfig | undefined

        // Handle 401 Unauthorized (but not for retry attempts or refresh endpoint)
        if (
          error.response?.status === 401 &&
          originalRequest &&
          !originalRequest._retry &&
          !originalRequest.url?.includes('/api/auth/refresh')
        ) {
          // Mark this request as a retry
          originalRequest._retry = true

          // If already refreshing, wait for the refresh to complete
          if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
              this.subscribeTokenRefresh((newToken: string) => {
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                resolve(this.client(originalRequest))
              })
              // Also handle the case where refresh fails
              setTimeout(() => {
                if (this.refreshSubscribers.length === 0) {
                  reject(error)
                }
              }, 10000) // 10 second timeout
            })
          }

          // Start refreshing
          this.isRefreshing = true
          const refreshToken = localStorage.getItem('vega_refresh_token')

          if (refreshToken) {
            try {
              // Use fetch instead of axios to avoid interceptor loops
              const response = await fetch(
                `${this.client.defaults.baseURL}/api/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`,
                {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                }
              )

              if (!response.ok) {
                throw new Error('Refresh failed')
              }

              const data = await response.json()
              const { access_token, refresh_token } = data.data

              localStorage.setItem('vega_access_token', access_token)
              localStorage.setItem('vega_refresh_token', refresh_token)

              // Notify all waiting requests
              this.onTokenRefreshed(access_token)
              this.isRefreshing = false

              // Retry original request
              originalRequest.headers.Authorization = `Bearer ${access_token}`
              return this.client(originalRequest)
            } catch {
              // Refresh failed
              this.onRefreshFailed()
              this.isRefreshing = false
              this.handleLogout()
              this.logApiError(error)
              return Promise.reject(error)
            }
          } else {
            this.isRefreshing = false
            this.handleLogout()
          }
        }

        this.logApiError(error)
        return Promise.reject(error)
      }
    )
  }

  private handleLogout() {
    const currentPath = window.location.pathname
    const isAuthPage = currentPath === '/login' || currentPath === '/register'

    if (!isAuthPage) {
      localStorage.removeItem('vega_access_token')
      localStorage.removeItem('vega_refresh_token')
      localStorage.removeItem('vega_user_id')

      // Dispatch logout event for Redux to handle
      window.dispatchEvent(new CustomEvent('auth:logout'))

      window.location.href = '/login'
    }
  }

  getClient(): AxiosInstance {
    return this.client
  }
}

export const apiClient = new ApiClient().getClient()

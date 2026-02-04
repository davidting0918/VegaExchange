import { apiClient } from '../client'
import type {
  ApiResponse,
  User,
  BalancesResponse,
  Balance,
  PortfolioResponse,
  Trade,
} from '../../types'

class UserService {
  private basePath = '/api/user'

  // Get current user info
  async getCurrentUser(): Promise<ApiResponse<User>> {
    const response = await apiClient.get(this.basePath)
    return response.data
  }

  // Get all balances
  // Backend returns array directly: [ { currency, available, locked, total }, ... ]
  async getBalances(): Promise<ApiResponse<Balance[] | BalancesResponse>> {
    const response = await apiClient.get(`${this.basePath}/balances`)
    return response.data
  }

  // Get balance for specific asset
  async getBalance(asset: string): Promise<ApiResponse<Balance>> {
    const response = await apiClient.get(`${this.basePath}/balance/${asset}`)
    return response.data
  }

  // Get portfolio with USDT valuation
  async getPortfolio(): Promise<ApiResponse<PortfolioResponse>> {
    const response = await apiClient.get(`${this.basePath}/portfolio`)
    return response.data
  }

  // Get user's trade history
  async getTrades(limit: number = 50): Promise<ApiResponse<Trade[]>> {
    const response = await apiClient.get(`${this.basePath}/trades`, {
      params: { limit },
    })
    return response.data
  }
}

export const userService = new UserService()

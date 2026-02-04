import { apiClient } from '../client'
import type { ApiResponse, Symbol, PoolInfo, Trade } from '../../types'

// Market data response
interface MarketData {
  symbol: string
  engine_type: number
  last_price: string
  price_24h_ago: string
  price_change_24h: string
  high_24h: string
  low_24h: string
  volume_24h: string
  quote_volume_24h: string
}

class MarketService {
  private basePath = '/api/market'

  // URL encode symbol for API paths (handles /, :, and other special chars)
  private encodeSymbol(symbol: string): string {
    return encodeURIComponent(symbol)
  }

  // Get all active symbols
  async getSymbols(): Promise<ApiResponse<Symbol[]>> {
    // Note: /list_symbols has route ordering issue in backend, use /api/market instead
    const response = await apiClient.get(this.basePath)
    // The /api/market endpoint returns { markets: [...] }, extract the array
    const data = response.data
    if (data.success && data.data?.markets) {
      return {
        success: true,
        data: data.data.markets.map((m: { 
          symbol: string
          base_asset: string
          quote_asset: string
          engine_type: number
          current_price?: number
        }) => ({
          symbol: m.symbol,
          base: m.base_asset,
          quote: m.quote_asset,
          engine_type: m.engine_type,
          market: 'spot', // Default to spot, backend should provide this
          current_price: m.current_price,
          is_active: true,
        })),
      }
    }
    return data
  }

  // Get symbol details
  async getSymbol(symbol: string): Promise<ApiResponse<Symbol>> {
    const response = await apiClient.get(`${this.basePath}/get_symbol/${this.encodeSymbol(symbol)}`)
    return response.data
  }

  // Get market data for a symbol
  async getMarketData(symbol: string): Promise<ApiResponse<MarketData>> {
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}`)
    return response.data
  }

  // Get all market data
  async getAllMarketData(): Promise<ApiResponse<MarketData[]>> {
    const response = await apiClient.get(this.basePath)
    return response.data
  }

  // Get AMM pool data
  async getPoolData(symbol: string): Promise<ApiResponse<PoolInfo>> {
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}/pool`)
    const data = response.data
    
    // Transform backend response to match PoolInfo type
    if (data.success && data.data) {
      const poolData = data.data
      // Extract base/quote from symbol (e.g., "ETH_USDT" -> base="ETH", quote="USDT")
      const [base, quote] = poolData.symbol.split('_')
      
      return {
        success: true,
        data: {
          pool_id: poolData.pool_id || '',
          symbol_id: poolData.symbol_id || 0,
          symbol: poolData.symbol,
          base: base || '',
          quote: quote || '',
          reserve_base: String(poolData.reserve_base),
          reserve_quote: String(poolData.reserve_quote),
          k_value: String(poolData.k_value),
          fee_rate: String(poolData.fee_rate),
          total_lp_shares: String(poolData.total_lp_shares),
          total_volume_base: String(poolData.total_volume_base),
          total_volume_quote: String(poolData.total_volume_quote),
          total_fees_collected: String(poolData.total_fees_collected),
          current_price: String(poolData.current_price),
        },
      }
    }
    return data
  }

  // Get recent trades for a symbol
  async getRecentTrades(symbol: string, limit: number = 50): Promise<ApiResponse<Trade[]>> {
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}/trades`, {
      params: { limit },
    })
    const data = response.data
    
    // Backend returns { symbol, trades: [...] }, extract trades array
    if (data.success && data.data?.trades) {
      return {
        success: true,
        data: data.data.trades,
      }
    }
    return data
  }

  // Get orderbook (for CLOB symbols)
  async getOrderbook(
    symbol: string,
    levels: number = 20
  ): Promise<
    ApiResponse<{
      bids: Array<{ price: string; quantity: string }>
      asks: Array<{ price: string; quantity: string }>
    }>
  > {
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}/orderbook`, {
      params: { levels },
    })
    return response.data
  }
}

export const marketService = new MarketService()

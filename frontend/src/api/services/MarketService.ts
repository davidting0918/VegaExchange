import { apiClient } from '../client'
import type { ApiResponse, Symbol, PoolInfo, Trade } from '../../types'
import { toPoolApiPath } from '../../utils/market'

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

// Engine type constants
const ENGINE_TYPE = {
  AMM: 0,
  CLOB: 1,
} as const

class MarketService {
  private basePath = '/api/market'

  // Convert symbol to pool API path format: {base}/{quote}/{settle}/{market}
  private toPoolPath(symbol: string): string {
    return toPoolApiPath(symbol)
  }

  // URL encode symbol for non-pool API paths
  private encodeSymbol(symbol: string): string {
    return encodeURIComponent(symbol)
  }

  // Get all active symbols
  async getSymbols(): Promise<ApiResponse<Symbol[]>> {
    // Use /api/market to get all markets
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
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}`)
    return response.data
  }

  // Get market data for a symbol
  async getMarketData(symbol: string, engineType?: number): Promise<ApiResponse<MarketData>> {
    const params = engineType !== undefined ? { engine_type: engineType } : {}
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}`, { params })
    return response.data
  }

  // Get all market data
  async getAllMarketData(): Promise<ApiResponse<MarketData[]>> {
    const response = await apiClient.get(this.basePath)
    return response.data
  }

  // Get AMM pool data - uses /api/pool/{base}/{quote}/{settle}/{market}
  async getPoolData(symbol: string): Promise<ApiResponse<PoolInfo>> {
    const response = await apiClient.get(`/api/pool/${this.toPoolPath(symbol)}`)
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
  // Uses /api/pool/{base}/{quote}/{settle}/{market}/trades for AMM or /api/orderbook/{symbol}/trades for CLOB
  async getRecentTrades(
    symbol: string,
    engineType: number = ENGINE_TYPE.AMM,
    limit: number = 50
  ): Promise<ApiResponse<Trade[]>> {
    // Choose endpoint based on engine type
    const endpoint = engineType === ENGINE_TYPE.AMM
      ? `/api/pool/${this.toPoolPath(symbol)}/trades`
      : `/api/orderbook/${this.encodeSymbol(symbol)}/trades`
    
    const response = await apiClient.get(endpoint, {
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

  // Get orderbook (for CLOB symbols) - now uses /api/orderbook/{symbol}
  async getOrderbook(
    symbol: string,
    levels: number = 20
  ): Promise<
    ApiResponse<{
      bids: Array<{ price: string; quantity: string }>
      asks: Array<{ price: string; quantity: string }>
    }>
  > {
    // New endpoint: GET /api/orderbook/{symbol}
    const response = await apiClient.get(`/api/orderbook/${this.encodeSymbol(symbol)}`, {
      params: { levels },
    })
    return response.data
  }

  // Get all AMM pools
  async getAllPools(): Promise<ApiResponse<PoolInfo[]>> {
    const response = await apiClient.get('/api/pool')
    const data = response.data
    
    if (data.success && data.data?.pools) {
      return {
        success: true,
        data: data.data.pools,
      }
    }
    return data
  }

  // Get all CLOB orderbook markets
  async getAllOrderbookMarkets(): Promise<ApiResponse<Symbol[]>> {
    const response = await apiClient.get('/api/orderbook')
    const data = response.data
    
    if (data.success && data.data?.markets) {
      return {
        success: true,
        data: data.data.markets,
      }
    }
    return data
  }

  // Get available engines for a symbol
  async getSymbolEngines(symbol: string): Promise<ApiResponse<{
    symbol: string
    engines: Array<{
      engine_type: number
      engine_name: string
      market_data: Record<string, unknown>
    }>
  }>> {
    const response = await apiClient.get(`${this.basePath}/${this.encodeSymbol(symbol)}/engines`)
    return response.data
  }
}

export const marketService = new MarketService()

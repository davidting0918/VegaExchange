import { apiClient } from '../client'
import { API, poolParams, orderbookParams, marketParams } from '../endpoints'
import type { ApiResponse, Symbol, PoolInfo, Trade, LPPosition } from '../../types'
import { parseSymbolToPath } from '../../utils/market'

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
  // Get all active symbols
  async getSymbols(): Promise<ApiResponse<Symbol[]>> {
    const response = await apiClient.get(API.market)
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
    const response = await apiClient.get(API.market, { params: marketParams(symbol) })
    return response.data
  }

  // Get market data for a symbol
  async getMarketData(symbol: string, engineType?: number): Promise<ApiResponse<MarketData>> {
    const params = engineType !== undefined ? marketParams(symbol, { engine_type: engineType }) : marketParams(symbol)
    const response = await apiClient.get(API.market, { params })
    return response.data
  }

  // Get all market data
  async getAllMarketData(): Promise<ApiResponse<MarketData[]>> {
    const response = await apiClient.get(API.market)
    return response.data
  }

  // Get AMM pool data
  async getPoolData(symbol: string): Promise<ApiResponse<PoolInfo>> {
    const response = await apiClient.get(API.pool, { params: poolParams(symbol) })
    const data = response.data
    
    // Transform backend response to match PoolInfo type
    if (data.success && data.data) {
      const poolData = data.data
      // Use explicit base/quote/settle/market from backend when provided; otherwise parse symbol (format: BASE/QUOTE-SETTLE:MARKET)
      const parsed = parseSymbolToPath(poolData.symbol)
      const base = poolData.base ?? parsed?.base ?? ''
      const quote = poolData.quote ?? parsed?.quote ?? ''

      return {
        success: true,
        data: {
          pool_id: poolData.pool_id || '',
          symbol_id: poolData.symbol_id || 0,
          symbol: poolData.symbol,
          base,
          quote,
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

  // Get public pool data + trades in one call (reduces API calls)
  async getPoolPublic(
    symbol: string,
    limit: number = 100
  ): Promise<ApiResponse<{ poolInfo: PoolInfo; trades: Trade[] }>> {
    const response = await apiClient.get(`${API.pool}/public`, {
      params: poolParams(symbol, { limit }),
    })
    const data = response.data
    if (data.success && data.data) {
      const d = data.data
      const parsed = parseSymbolToPath(d.symbol)
      const base = d.base ?? parsed?.base ?? ''
      const quote = d.quote ?? parsed?.quote ?? ''
      const poolInfo: PoolInfo = {
        pool_id: d.pool_id || '',
        symbol_id: d.symbol_id || 0,
        symbol: d.symbol,
        base,
        quote,
        reserve_base: String(d.reserve_base),
        reserve_quote: String(d.reserve_quote),
        k_value: String(d.k_value),
        fee_rate: String(d.fee_rate),
        total_lp_shares: String(d.total_lp_shares),
        total_volume_base: String(d.total_volume_base),
        total_volume_quote: String(d.total_volume_quote),
        total_fees_collected: String(d.total_fees_collected),
        current_price: String(d.current_price),
      }
      const trades = (d.trades || []).map((t: Record<string, unknown>) => ({
        ...t,
        side: t.side === 0 ? 'buy' : 'sell',
        price: t.price != null ? String(t.price) : '0',
        quantity: t.quantity != null ? String(t.quantity) : '0',
        quote_amount: t.quote_amount != null ? String(t.quote_amount) : '0',
        fee_amount: t.fee_amount != null ? String(t.fee_amount) : '0',
      })) as Trade[]
      return { success: true, data: { poolInfo, trades } }
    }
    return data
  }

  // Get user-specific pool data (LP position + balances). Requires auth.
  async getPoolUser(
    symbol: string
  ): Promise<ApiResponse<{ lpPosition: LPPosition | null; baseBalance: string; quoteBalance: string }>> {
    const response = await apiClient.get(`${API.pool}/user`, { params: poolParams(symbol) })
    const data = response.data
    if (data.success && data.data) {
      const d = data.data
      const lpPosition: LPPosition | null = d.lp_position
        ? {
            pool_id: d.lp_position.pool_id || '',
            symbol: d.symbol,
            lp_shares: String(d.lp_position.lp_shares),
            share_percentage: String(d.lp_position.share_percentage ?? 0),
            base_amount: String(d.lp_position.estimated_base_value ?? 0),
            quote_amount: String(d.lp_position.estimated_quote_value ?? 0),
            initial_base_amount: String(d.lp_position.initial_base_amount ?? 0),
            initial_quote_amount: String(d.lp_position.initial_quote_amount ?? 0),
          }
        : null
      return {
        success: true,
        data: {
          lpPosition,
          baseBalance: String(d.base_balance ?? '0'),
          quoteBalance: String(d.quote_balance ?? '0'),
        },
      }
    }
    return data
  }

  // Get recent trades for a symbol
  async getRecentTrades(
    symbol: string,
    engineType: number = ENGINE_TYPE.AMM,
    limit: number = 50
  ): Promise<ApiResponse<Trade[]>> {
    const endpoint = engineType === ENGINE_TYPE.AMM ? `${API.pool}/trades` : `${API.orderbook}/trades`
    const params = engineType === ENGINE_TYPE.AMM ? poolParams(symbol, { limit }) : orderbookParams(symbol, { limit })
    const response = await apiClient.get(endpoint, { params })
    const data = response.data
    
    // Backend returns { symbol, trades: [...] }; side is 0 (BUY) or 1 (SELL), normalize to 'buy' | 'sell'
    if (data.success && data.data?.trades) {
      const trades = (data.data.trades as Array<Record<string, unknown>>).map((t) => ({
        ...t,
        side: t.side === 0 ? 'buy' : 'sell',
        price: t.price != null ? String(t.price) : '0',
        quantity: t.quantity != null ? String(t.quantity) : '0',
        quote_amount: t.quote_amount != null ? String(t.quote_amount) : '0',
        fee_amount: t.fee_amount != null ? String(t.fee_amount) : '0',
      }))
      return {
        success: true,
        data: trades as Trade[],
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
    const response = await apiClient.get(API.orderbook, {
      params: orderbookParams(symbol, { levels }),
    })
    return response.data
  }

  // Get all AMM pools
  async getAllPools(): Promise<ApiResponse<PoolInfo[]>> {
    const response = await apiClient.get(API.pool)
    const data = response.data
    
    if (data.success && data.data?.pools) {
      const pools = data.data.pools as Array<Record<string, unknown>>
      return {
        success: true,
        data: pools.map((p) => ({
          pool_id: String(p.pool_id ?? ''),
          symbol_id: Number(p.symbol_id ?? 0),
          symbol: String(p.symbol ?? ''),
          base: String(p.base ?? ''),
          quote: String(p.quote ?? ''),
          reserve_base: String(p.reserve_base ?? 0),
          reserve_quote: String(p.reserve_quote ?? 0),
          k_value: String(p.k_value ?? 0),
          fee_rate: String(p.fee_rate ?? 0),
          total_lp_shares: String(p.total_lp_shares ?? 0),
          total_volume_base: String(p.total_volume_base ?? 0),
          total_volume_quote: String(p.total_volume_quote ?? 0),
          total_fees_collected: String(p.total_fees_collected ?? 0),
          current_price: String(p.current_price ?? 0),
        })),
      }
    }
    return data
  }

  // Get all CLOB orderbook markets
  async getAllOrderbookMarkets(): Promise<ApiResponse<Symbol[]>> {
    const response = await apiClient.get(API.orderbook)
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
    const response = await apiClient.get(`${API.market}/engines`, { params: marketParams(symbol) })
    return response.data
  }
}

export const marketService = new MarketService()

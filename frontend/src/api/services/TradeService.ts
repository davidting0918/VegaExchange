import { apiClient } from '../client'
import type {
  ApiResponse,
  QuoteRequest,
  QuoteResponse,
  SwapRequest,
  Trade,
  AddLiquidityRequest,
  RemoveLiquidityRequest,
  LiquidityResponse,
  LPPosition,
  LPEvent,
} from '../../types'
import { toPoolApiPath } from '../../utils/market'

class TradeService {
  // Convert symbol to pool API path format: {base}/{quote}/{settle}/{market}
  private toPoolPath(symbol: string): string {
    return toPoolApiPath(symbol)
  }

  // Get trade quote (preview) - AMM only
  async getQuote(request: QuoteRequest): Promise<ApiResponse<QuoteResponse>> {
    // New endpoint: GET /api/pool/{symbol}/quote
    // Query params: side, quantity (base) or quote_amount (quote)
    const params: Record<string, string> = {
      side: request.side,
    }
    
    // Determine which parameter to use based on amount_type
    if (request.amount_type === 'quote') {
      params.quote_amount = request.amount
    } else {
      params.quantity = request.amount
    }
    
    const response = await apiClient.get(
      `/api/pool/${this.toPoolPath(request.symbol)}/quote`,
      { params }
    )
    const data = response.data
    
    // Transform backend response to match QuoteResponse type
    if (data.success && data.data) {
      const q = data.data
      return {
        success: true,
        data: {
          symbol: q.symbol,
          side: q.side,
          input_amount: String(q.input_amount),
          output_amount: String(q.output_amount),
          price: String(q.effective_price),
          price_impact: String(q.price_impact || 0),
          fee_amount: String(q.fee_amount),
          fee_asset: q.fee_asset,
        },
      }
    }
    return data
  }

  // Execute swap - AMM only
  async swap(request: SwapRequest): Promise<ApiResponse<Trade>> {
    // New endpoint: POST /api/pool/{symbol}/swap
    // Body: { symbol, side, amount_in, min_amount_out }
    const backendRequest = {
      symbol: request.symbol,
      side: request.side,
      amount_in: request.amount,
      min_amount_out: request.min_output,
    }
    
    const response = await apiClient.post(
      `/api/pool/${this.toPoolPath(request.symbol)}/swap`,
      backendRequest
    )
    return response.data
  }

  // Add liquidity to AMM pool
  async addLiquidity(request: AddLiquidityRequest): Promise<ApiResponse<LiquidityResponse>> {
    // New endpoint: POST /api/pool/{symbol}/liquidity/add
    const response = await apiClient.post(
      `/api/pool/${this.toPoolPath(request.symbol)}/liquidity/add`,
      request
    )
    return response.data
  }

  // Remove liquidity from AMM pool
  async removeLiquidity(request: RemoveLiquidityRequest): Promise<ApiResponse<LiquidityResponse>> {
    // New endpoint: POST /api/pool/{symbol}/liquidity/remove
    const response = await apiClient.post(
      `/api/pool/${this.toPoolPath(request.symbol)}/liquidity/remove`,
      request
    )
    return response.data
  }

  // Get user's LP position for a pool
  async getLPPosition(symbol: string): Promise<ApiResponse<LPPosition>> {
    // New endpoint: GET /api/pool/{symbol}/liquidity/position
    const response = await apiClient.get(
      `/api/pool/${this.toPoolPath(symbol)}/liquidity/position`
    )
    const data = response.data
    
    // Transform backend response to match LPPosition type
    if (data.success && data.data) {
      const pos = data.data
      return {
        success: true,
        data: {
          pool_id: pos.pool_id || '',
          symbol: pos.symbol,
          lp_shares: String(pos.lp_shares),
          share_percentage: String(pos.pool_share_percentage || 0),
          base_amount: String(pos.estimated_base_value || 0),
          quote_amount: String(pos.estimated_quote_value || 0),
          initial_base_amount: String(pos.initial_base_amount || 0),
          initial_quote_amount: String(pos.initial_quote_amount || 0),
        },
      }
    }
    return data
  }

  // Get liquidity event history
  async getLPHistory(symbol: string, limit: number = 50): Promise<ApiResponse<LPEvent[]>> {
    // New endpoint: GET /api/pool/{symbol}/liquidity/history
    // Note: limit is not supported by the new endpoint, but we keep the param for future use
    const response = await apiClient.get(
      `/api/pool/${this.toPoolPath(symbol)}/liquidity/history`
    )
    const data = response.data
    
    // Extract events array from response
    if (data.success && data.data?.events) {
      return {
        success: true,
        data: data.data.events.slice(0, limit),
      }
    }
    return data
  }

  // Get user's trade history - now uses /api/user/trades
  async getTradeHistory(
    symbol?: string,
    engineType?: number,
    limit: number = 50
  ): Promise<ApiResponse<Trade[]>> {
    // New endpoint: GET /api/user/trades
    const response = await apiClient.get('/api/user/trades', {
      params: {
        symbol,
        engine_type: engineType,
        limit,
      },
    })
    return response.data
  }
}

export const tradeService = new TradeService()

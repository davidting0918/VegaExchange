import { apiClient } from '../client'
import { API, poolParams, orderbookParams } from '../endpoints'
import type {
  ApiResponse,
  QuoteRequest,
  QuoteResponse,
  SwapRequest,
  Trade,
  AddLiquidityRequest,
  AddLiquidityQuoteResponse,
  RemoveLiquidityRequest,
  LiquidityResponse,
  LPPosition,
  LPEvent,
  VolumeDataPoint,
  PlaceOrderRequest,
  Order,
  OrderStatus,
} from '../../types'

// Map backend integer status to frontend string
const ORDER_STATUS_MAP: Record<number, OrderStatus> = {
  0: 'pending',
  1: 'partial',
  2: 'filled',
  3: 'cancelled',
}

class TradeService {
  private sideToInt(side: string): number {
    return side.toLowerCase() === 'buy' ? 0 : 1
  }

  private orderTypeToInt(type: string): number {
    return type.toLowerCase() === 'market' ? 0 : 1
  }

  // Place an order on the CLOB orderbook
  async placeOrder(request: PlaceOrderRequest): Promise<ApiResponse<Record<string, unknown>>> {
    const backendRequest = {
      symbol: request.symbol,
      side: this.sideToInt(request.side),
      order_type: this.orderTypeToInt(request.order_type),
      quantity: request.quantity,
      ...(request.price != null && request.order_type === 'limit' ? { price: request.price } : {}),
    }
    const response = await apiClient.post(`${API.orderbook}/order`, backendRequest, {
      params: { symbol: request.symbol },
    })
    return response.data
  }

  // Cancel an order on the CLOB orderbook
  async cancelOrder(symbol: string, orderId: string): Promise<ApiResponse<unknown>> {
    const response = await apiClient.post(`${API.orderbook}/order/cancel`, null, {
      params: { symbol, order_id: orderId },
    })
    return response.data
  }

  // Get a quote for an orderbook trade
  async getOrderbookQuote(
    symbol: string,
    side: string,
    quantity: string
  ): Promise<ApiResponse<Record<string, unknown>>> {
    const response = await apiClient.get(`${API.orderbook}/quote`, {
      params: orderbookParams(symbol, { side: this.sideToInt(side), quantity }),
    })
    return response.data
  }

  // Get user's orders for a specific symbol
  async getUserOrders(
    symbol: string,
    status?: OrderStatus[],
    limit: number = 50
  ): Promise<ApiResponse<Order[]>> {
    const statusInts = status?.map(s => {
      const entry = Object.entries(ORDER_STATUS_MAP).find(([, v]) => v === s)
      return entry ? Number(entry[0]) : undefined
    }).filter((v): v is number => v !== undefined)

    const response = await apiClient.get(`${API.orderbook}/orders`, {
      params: {
        symbol,
        ...(statusInts && statusInts.length > 0 ? { status: statusInts } : {}),
        limit,
      },
    })
    const data = response.data
    if (data.success && data.data?.orders) {
      return {
        success: true,
        data: this.normalizeOrders(data.data.orders),
      }
    }
    return data
  }

  // Get all user orders across symbols
  async getAllUserOrders(
    status?: OrderStatus[],
    symbol?: string,
    limit: number = 50
  ): Promise<ApiResponse<Order[]>> {
    const statusInts = status?.map(s => {
      const entry = Object.entries(ORDER_STATUS_MAP).find(([, v]) => v === s)
      return entry ? Number(entry[0]) : undefined
    }).filter((v): v is number => v !== undefined)

    const response = await apiClient.get(`${API.orderbook}/user/orders`, {
      params: {
        ...(symbol ? { symbol } : {}),
        ...(statusInts && statusInts.length > 0 ? { status: statusInts } : {}),
        limit,
      },
    })
    const data = response.data
    if (data.success && data.data?.orders) {
      return {
        success: true,
        data: this.normalizeOrders(data.data.orders),
      }
    }
    return data
  }

  // Normalize backend order records to frontend Order type
  private normalizeOrders(orders: Array<Record<string, unknown>>): Order[] {
    return orders.map(o => ({
      order_id: String(o.order_id),
      symbol: String(o.symbol),
      side: (o.side === 0 ? 'buy' : 'sell') as Order['side'],
      order_type: (o.order_type === 0 ? 'market' : 'limit') as Order['order_type'],
      price: String(o.price ?? '0'),
      quantity: String(o.quantity ?? '0'),
      filled_quantity: String(o.filled_quantity ?? '0'),
      remaining_quantity: String(o.remaining_quantity ?? '0'),
      status: ORDER_STATUS_MAP[o.status as number] ?? 'pending',
      created_at: String(o.created_at ?? ''),
      updated_at: o.updated_at ? String(o.updated_at) : undefined,
    }))
  }

  // Get trade quote (preview) - AMM only
  async getQuote(request: QuoteRequest): Promise<ApiResponse<QuoteResponse>> {
    const params = request.amount_type === 'quote'
      ? poolParams(request.symbol, { side: this.sideToInt(request.side), quote_amount: request.amount })
      : poolParams(request.symbol, { side: this.sideToInt(request.side), quantity: request.amount })
    const response = await apiClient.get(`${API.pool}/quote`, { params })
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
    const backendRequest: Record<string, unknown> = {
      symbol: request.symbol,
      side: this.sideToInt(request.side),
      amount_in: request.amount,
    }
    if (request.min_output != null && request.min_output !== '') {
      backendRequest.min_amount_out = request.min_output
    }

    const response = await apiClient.post(`${API.pool}/swap`, backendRequest)
    return response.data
  }

  // Get quote for adding liquidity (given base_amount returns quote_amount, or vice versa)
  async getAddLiquidityQuote(
    symbol: string,
    baseAmount?: string,
    quoteAmount?: string
  ): Promise<ApiResponse<AddLiquidityQuoteResponse>> {
    const extra: Record<string, string> = {}
    if (baseAmount != null && baseAmount !== '') extra.base_amount = baseAmount
    else if (quoteAmount != null && quoteAmount !== '') extra.quote_amount = quoteAmount
    else throw new Error('Provide base_amount or quote_amount')
    const params = poolParams(symbol, extra)
    const response = await apiClient.get(`${API.pool}/liquidity/add/quote`, { params })
    const data = response.data
    if (data.success && data.data) {
      const q = data.data
      return {
        success: true,
        data: {
          base_amount: String(q.base_amount),
          quote_amount: String(q.quote_amount),
        },
      }
    }
    return data
  }

  // Add liquidity to AMM pool
  async addLiquidity(request: AddLiquidityRequest): Promise<ApiResponse<LiquidityResponse>> {
    const response = await apiClient.post(`${API.pool}/liquidity/add`, request)
    return response.data
  }

  // Remove liquidity from AMM pool
  async removeLiquidity(request: RemoveLiquidityRequest): Promise<ApiResponse<LiquidityResponse>> {
    const response = await apiClient.post(`${API.pool}/liquidity/remove`, request)
    return response.data
  }

  // Get user's LP position for a pool
  async getLPPosition(symbol: string): Promise<ApiResponse<LPPosition>> {
    const response = await apiClient.get(`${API.pool}/liquidity/position`, {
      params: poolParams(symbol),
    })
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
    const response = await apiClient.get(`${API.pool}/liquidity/history`, {
      params: poolParams(symbol),
    })
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

  // Pool chart: volume by time bucket (public)
  async getPoolVolumeChart(
    symbol: string,
    period: '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL' = '1D',
    limit: number = 100
  ): Promise<ApiResponse<{ buckets: VolumeDataPoint[]; base?: string; quote?: string }>> {
    const response = await apiClient.get(`${API.pool}/chart/volume`, {
      params: poolParams(symbol, { period, limit }),
    })
    const data = response.data
    if (data.success && data.data?.buckets) {
      return {
        success: true,
        data: {
          buckets: data.data.buckets.map((b: { time: string; volume: number }) => ({
            time: b.time,
            volume: Number(b.volume),
          })),
          base: data.data.base,
          quote: data.data.quote,
        },
      }
    }
    return data
  }

  // Pool chart: price history from trades (public)
  async getPoolPriceHistory(
    symbol: string,
    period: '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL' = '1D',
    limit: number = 500
  ): Promise<
    ApiResponse<{ prices: { time: string; price: number }[]; base?: string; quote?: string }>
  > {
    const response = await apiClient.get(`${API.pool}/chart/price-history`, {
      params: poolParams(symbol, { period, limit }),
    })
    const data = response.data
    if (data.success && data.data?.prices) {
      return {
        success: true,
        data: {
          prices: data.data.prices.map((p: { time: string; price: number }) => ({
            time: p.time,
            price: Number(p.price),
          })),
          base: data.data.base,
          quote: data.data.quote,
        },
      }
    }
    return data
  }

  // Get user's trade history
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

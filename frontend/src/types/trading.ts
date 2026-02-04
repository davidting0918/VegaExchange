// Symbol types
export type MarketType = 'spot' | 'perp' | 'option' | 'future'
export type EngineType = 0 | 1 // 0 = AMM, 1 = CLOB
export type TradeSide = 'buy' | 'sell'

// Symbol configuration
export interface Symbol {
  symbol_id?: number
  symbol: string
  market?: MarketType
  base: string
  quote: string
  settle?: string
  engine_type: EngineType
  min_trade_amount?: string
  max_trade_amount?: string
  price_precision?: number
  quantity_precision?: number
  is_active?: boolean
  current_price?: number
}

// AMM Pool info
export interface PoolInfo {
  pool_id: string
  symbol_id: number
  symbol: string
  base: string
  quote: string
  reserve_base: string
  reserve_quote: string
  k_value: string
  fee_rate: string
  total_lp_shares: string
  total_volume_base: string
  total_volume_quote: string
  total_fees_collected: string
  current_price: string
}

// Trade quote request
export interface QuoteRequest {
  symbol: string
  side: TradeSide
  amount: string
  amount_type?: 'base' | 'quote'
}

// Trade quote response
export interface QuoteResponse {
  symbol: string
  side: TradeSide
  input_amount: string
  output_amount: string
  price: string
  price_impact: string
  fee_amount: string
  fee_asset: string
  min_output?: string
}

// Swap request
export interface SwapRequest {
  symbol: string
  side: TradeSide
  amount: string
  amount_type?: 'base' | 'quote'
  slippage_tolerance?: number
  min_output?: string
}

// Trade response
export interface Trade {
  trade_id: string
  symbol: string
  side: TradeSide
  engine_type: EngineType
  price: string
  quantity: string
  quote_amount: string
  fee_amount: string
  fee_asset: string
  status: number
  created_at: string
}

// Add liquidity request
export interface AddLiquidityRequest {
  symbol: string
  base_amount: string
  quote_amount: string
}

// Remove liquidity request (backend expects lp_shares, not percentage)
export interface RemoveLiquidityRequest {
  symbol: string
  lp_shares: string
}

// LP Position
export interface LPPosition {
  pool_id: string
  symbol: string
  lp_shares: string
  share_percentage: string
  base_amount: string
  quote_amount: string
  initial_base_amount: string
  initial_quote_amount: string
}

// LP Event
export interface LPEvent {
  id: number
  pool_id: string
  user_id: string
  event_type: 'add' | 'remove'
  lp_shares: string
  base_amount: string
  quote_amount: string
  created_at: string
}

// Liquidity operation response
export interface LiquidityResponse {
  lp_shares: string
  base_amount: string
  quote_amount: string
  share_percentage: string
}

// Trading state
export interface TradingState {
  symbols: Symbol[]
  currentSymbol: string | null
  poolInfo: PoolInfo | null
  lpPosition: LPPosition | null
  quote: QuoteResponse | null
  recentTrades: Trade[]
  isLoading: boolean
  isQuoteLoading: boolean
  error: string | null
}

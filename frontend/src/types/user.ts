// User model
export interface User {
  user_id: string
  user_name: string
  email: string
  photo_url?: string
  is_admin: boolean
  is_active: boolean
  created_at?: string
  last_login_at?: string
}

// User balance
export interface Balance {
  currency: string
  available: string
  balance: string
  locked: string
}

// User balances response
export interface BalancesResponse {
  balances: Balance[]
  total_available: string
  total_balance: string
  total_locked: string
}

// Portfolio item
export interface PortfolioItem {
  currency: string
  balance: string
  available: string
  locked: string
  price_usdt: string
  value_usdt: string
}

// Portfolio response
export interface PortfolioResponse {
  items: PortfolioItem[]
  total_value_usdt: string
}

// User state
export interface UserState {
  user: User | null
  balances: Balance[]
  portfolio: PortfolioItem[]
  totalValueUsdt: string
  isLoading: boolean
  error: string | null
}

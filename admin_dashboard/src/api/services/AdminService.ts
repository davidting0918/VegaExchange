import client from '@/api/client'
import type { APIResponse } from '@/types/admin'

export const AdminService = {
  // ── Settings ──
  async getSettings(): Promise<APIResponse> {
    const res = await client.get('/api/admin/settings')
    return res.data
  },

  async updateSetting(key: string, value: unknown): Promise<APIResponse> {
    const res = await client.post(`/api/admin/settings/update/${encodeURIComponent(key)}`, { value })
    return res.data
  },

  // ── Whitelist ──
  async getWhitelist(): Promise<APIResponse> {
    const res = await client.get('/api/admin/whitelist')
    return res.data
  },

  async addWhitelist(email: string, description?: string): Promise<APIResponse> {
    const res = await client.post('/api/admin/whitelist', { email, description })
    return res.data
  },

  async removeWhitelist(id: number): Promise<APIResponse> {
    const res = await client.post(`/api/admin/whitelist/remove/${id}`)
    return res.data
  },

  // ── Audit Log ──
  async getAuditLog(params: {
    admin_id?: string
    action?: string
    target_type?: string
    date_from?: string
    date_to?: string
    limit?: number
    offset?: number
  }): Promise<APIResponse> {
    const res = await client.get('/api/admin/audit-log', { params })
    return res.data
  },

  // ── Symbols ──
  async getSymbols(params?: {
    engine_type?: number
    is_active?: boolean
    market?: string
  }): Promise<APIResponse> {
    const res = await client.get('/api/admin/symbols', { params })
    return res.data
  },

  async getSymbol(symbolId: number): Promise<APIResponse> {
    const res = await client.get(`/api/admin/symbols/${symbolId}`)
    return res.data
  },

  async createSymbol(data: {
    symbol: string
    base_asset: string
    quote_asset: string
    market?: string
    settle?: string
    engine_type: number
    engine_params?: Record<string, unknown>
    min_trade_amount?: number
    max_trade_amount?: number
    price_precision?: number
    quantity_precision?: number
  }): Promise<APIResponse> {
    const res = await client.post('/api/admin/create_symbol', data)
    return res.data
  },

  async createPool(data: {
    symbol: string
    base_asset: string
    quote_asset: string
    market?: string
    settle?: string
    initial_reserve_base: number
    initial_reserve_quote: number
    fee_rate?: number
    price_precision?: number
    quantity_precision?: number
  }): Promise<APIResponse> {
    const res = await client.post('/api/admin/create_pool', data)
    return res.data
  },

  async updateSymbol(symbolId: number, data: {
    engine_params?: Record<string, unknown>
    min_trade_amount?: number
    max_trade_amount?: number
    price_precision?: number
    quantity_precision?: number
    fee_rate?: number
  }): Promise<APIResponse> {
    const res = await client.post(`/api/admin/symbols/update/${symbolId}`, data)
    return res.data
  },

  async updateSymbolStatus(symbol: string, status: string): Promise<APIResponse> {
    const res = await client.post(`/api/admin/update_symbol_status/${encodeURIComponent(symbol)}?status=${status}`)
    return res.data
  },

  async deleteSymbol(symbol: string): Promise<APIResponse> {
    const res = await client.post(`/api/admin/delete_symbol/${encodeURIComponent(symbol)}`)
    return res.data
  },
}

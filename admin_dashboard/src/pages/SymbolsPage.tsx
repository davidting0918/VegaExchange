import { useEffect, useState, useCallback } from 'react'
import { AdminService } from '@/api/services/AdminService'

interface SymbolConfig {
  symbol_id: number
  symbol: string
  base: string
  quote: string
  market: string
  settle: string
  engine_type: number
  engine_params: Record<string, unknown>
  min_trade_amount: number
  max_trade_amount: number
  price_precision: number
  quantity_precision: number
  is_active: boolean
  created_at: string
}

type ModalType = 'create_clob' | 'create_pool' | 'edit' | null

export function SymbolsPage() {
  const [symbols, setSymbols] = useState<SymbolConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<ModalType>(null)
  const [editTarget, setEditTarget] = useState<SymbolConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [confirmDeleteSymbol, setConfirmDeleteSymbol] = useState<string | null>(null)

  // Filter
  const [engineFilter, setEngineFilter] = useState<string>('')

  // Create CLOB form
  const [clobForm, setClobForm] = useState({
    base_asset: '', quote_asset: '', market: 'SPOT', settle: '',
    price_precision: 8, quantity_precision: 8,
  })

  // Create Pool form
  const [poolForm, setPoolForm] = useState({
    base_asset: '', quote_asset: '', market: 'SPOT', settle: '',
    initial_reserve_base: 1000, initial_reserve_quote: 1000,
    fee_rate: 0.003, price_precision: 8, quantity_precision: 8,
  })

  // Edit form
  const [editForm, setEditForm] = useState({
    min_trade_amount: 0, max_trade_amount: 0,
    price_precision: 8, quantity_precision: 8, fee_rate: 0,
  })

  const loadSymbols = useCallback(async () => {
    try {
      const params: Record<string, unknown> = {}
      if (engineFilter) params.engine_type = parseInt(engineFilter)
      const res = await AdminService.getSymbols(params as Parameters<typeof AdminService.getSymbols>[0])
      if (res.success && res.data) setSymbols(res.data as SymbolConfig[])
    } catch (err) {
      console.error('Failed to load symbols:', err)
    } finally {
      setLoading(false)
    }
  }, [engineFilter])

  useEffect(() => { loadSymbols() }, [loadSymbols])

  const buildSymbol = (base: string, quote: string, settle: string, market: string) => {
    const s = settle || quote
    return `${base.toUpperCase()}/${quote.toUpperCase()}-${s.toUpperCase()}:${market.toUpperCase()}`
  }

  const handleCreateClob = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const symbol = buildSymbol(clobForm.base_asset, clobForm.quote_asset, clobForm.settle || clobForm.quote_asset, clobForm.market)
      const res = await AdminService.createSymbol({
        symbol,
        base_asset: clobForm.base_asset.toUpperCase(),
        quote_asset: clobForm.quote_asset.toUpperCase(),
        market: clobForm.market.toUpperCase(),
        settle: (clobForm.settle || clobForm.quote_asset).toUpperCase(),
        engine_type: 1,
        price_precision: clobForm.price_precision,
        quantity_precision: clobForm.quantity_precision,
      })
      if (res.success) {
        setMessage({ text: `CLOB symbol ${symbol} created.`, type: 'success' })
        setModal(null)
        setClobForm({ base_asset: '', quote_asset: '', market: 'SPOT', settle: '', price_precision: 8, quantity_precision: 8 })
        loadSymbols()
      }
    } catch (err) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setMessage({ text: axiosErr.response?.data?.detail || 'Failed to create symbol', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleCreatePool = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const symbol = buildSymbol(poolForm.base_asset, poolForm.quote_asset, poolForm.settle || poolForm.quote_asset, poolForm.market)
      const res = await AdminService.createPool({
        symbol,
        base_asset: poolForm.base_asset.toUpperCase(),
        quote_asset: poolForm.quote_asset.toUpperCase(),
        market: poolForm.market.toUpperCase(),
        settle: (poolForm.settle || poolForm.quote_asset).toUpperCase(),
        initial_reserve_base: poolForm.initial_reserve_base,
        initial_reserve_quote: poolForm.initial_reserve_quote,
        fee_rate: poolForm.fee_rate,
        price_precision: poolForm.price_precision,
        quantity_precision: poolForm.quantity_precision,
      })
      if (res.success) {
        setMessage({ text: `AMM pool ${symbol} created.`, type: 'success' })
        setModal(null)
        loadSymbols()
      }
    } catch (err) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setMessage({ text: axiosErr.response?.data?.detail || 'Failed to create pool', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const openEdit = (s: SymbolConfig) => {
    setEditTarget(s)
    setEditForm({
      min_trade_amount: s.min_trade_amount,
      max_trade_amount: s.max_trade_amount,
      price_precision: s.price_precision,
      quantity_precision: s.quantity_precision,
      fee_rate: (s.engine_params as { fee_rate?: number })?.fee_rate || (s.engine_params as { maker_fee?: number })?.maker_fee || 0,
    })
    setModal('edit')
  }

  const handleEdit = async () => {
    if (!editTarget) return
    setSaving(true)
    setMessage(null)
    try {
      const res = await AdminService.updateSymbol(editTarget.symbol_id, {
        min_trade_amount: editForm.min_trade_amount,
        max_trade_amount: editForm.max_trade_amount,
        price_precision: editForm.price_precision,
        quantity_precision: editForm.quantity_precision,
        fee_rate: editForm.fee_rate || undefined,
      })
      if (res.success) {
        setMessage({ text: `Symbol ${editTarget.symbol} updated.`, type: 'success' })
        setModal(null)
        setEditTarget(null)
        loadSymbols()
      }
    } catch (err) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setMessage({ text: axiosErr.response?.data?.detail || 'Failed to update', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleToggleStatus = async (s: SymbolConfig) => {
    try {
      const newStatus = s.is_active ? 'MAINTENANCE' : 'ACTIVE'
      await AdminService.updateSymbolStatus(s.symbol, newStatus)
      loadSymbols()
    } catch (err) {
      console.error('Failed to toggle status:', err)
    }
  }

  const handleDelete = async (symbol: string) => {
    if (confirmDeleteSymbol !== symbol) {
      setConfirmDeleteSymbol(symbol)
      return
    }
    try {
      await AdminService.deleteSymbol(symbol)
      setMessage({ text: `Symbol ${symbol} deleted.`, type: 'success' })
      setConfirmDeleteSymbol(null)
      loadSymbols()
    } catch (err) {
      console.error('Failed to delete:', err)
      setMessage({ text: 'Failed to delete symbol', type: 'error' })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-5 h-5 border-2 border-text-tertiary border-t-accent-blue rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-1">Symbols</h2>
          <p className="text-sm text-text-tertiary">Manage trading pairs and AMM pools.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setModal('create_clob')}
            className="px-4 py-2 text-sm bg-accent-blue text-white rounded-md hover:bg-accent-blue/80"
          >
            + CLOB Symbol
          </button>
          <button
            onClick={() => setModal('create_pool')}
            className="px-4 py-2 text-sm bg-accent-green text-white rounded-md hover:bg-accent-green/80"
          >
            + AMM Pool
          </button>
        </div>
      </div>

      {message && (
        <div className={`mb-4 p-3 text-sm rounded-lg ${
          message.type === 'success'
            ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
            : 'bg-accent-red/10 text-accent-red border border-accent-red/20'
        }`}>
          {message.text}
        </div>
      )}

      {/* Filter */}
      <div className="mb-4 flex gap-2">
        {['', '0', '1'].map((val) => (
          <button
            key={val}
            onClick={() => setEngineFilter(val)}
            className={`px-3 py-1 text-xs rounded-md ${
              engineFilter === val
                ? 'bg-accent-blue text-white'
                : 'text-text-secondary border border-border-default hover:border-border-hover'
            }`}
          >
            {val === '' ? 'All' : val === '0' ? 'AMM' : 'CLOB'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="border border-border-default rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default bg-bg-secondary">
              <th className="px-4 py-3 font-medium">Symbol</th>
              <th className="px-4 py-3 font-medium">Engine</th>
              <th className="px-4 py-3 font-medium">Base / Quote</th>
              <th className="px-4 py-3 font-medium">Precision</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {symbols.map((s) => (
              <tr key={s.symbol_id} className="text-sm">
                <td className="px-4 py-3 font-mono text-text-primary">{s.symbol}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    s.engine_type === 0
                      ? 'bg-accent-green/10 text-accent-green'
                      : 'bg-accent-blue/10 text-accent-blue'
                  }`}>
                    {s.engine_type === 0 ? 'AMM' : 'CLOB'}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-secondary">{s.base} / {s.quote}</td>
                <td className="px-4 py-3 text-text-tertiary text-xs">
                  P:{s.price_precision} Q:{s.quantity_precision}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggleStatus(s)}
                    className={`px-2 py-0.5 text-xs rounded cursor-pointer ${
                      s.is_active
                        ? 'bg-accent-green/10 text-accent-green'
                        : 'bg-accent-yellow/10 text-accent-yellow'
                    }`}
                  >
                    {s.is_active ? 'Active' : 'Maintenance'}
                  </button>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={() => openEdit(s)}
                      className="px-2 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-default rounded-md"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(s.symbol)}
                      className={`px-2 py-1 text-xs rounded-md border ${
                        confirmDeleteSymbol === s.symbol
                          ? 'bg-accent-red/10 text-accent-red border-accent-red/20'
                          : 'text-text-tertiary hover:text-accent-red border-border-default'
                      }`}
                    >
                      {confirmDeleteSymbol === s.symbol ? 'Confirm' : 'Delete'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {symbols.length === 0 && (
          <div className="text-center py-8 text-text-tertiary text-sm">No symbols found.</div>
        )}
      </div>

      {/* ── Modals ── */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setModal(null)}>
          <div className="bg-bg-secondary border border-border-default rounded-lg p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>

            {/* Create CLOB */}
            {modal === 'create_clob' && (
              <>
                <h3 className="text-lg font-semibold text-text-primary mb-4">Create CLOB Symbol</h3>
                <div className="space-y-3">
                  <FormField label="Base Asset" value={clobForm.base_asset} onChange={(v) => setClobForm({ ...clobForm, base_asset: v })} placeholder="BTC" />
                  <FormField label="Quote Asset" value={clobForm.quote_asset} onChange={(v) => setClobForm({ ...clobForm, quote_asset: v })} placeholder="USDT" />
                  <FormField label="Market" value={clobForm.market} onChange={(v) => setClobForm({ ...clobForm, market: v })} placeholder="SPOT" />
                  <FormField label="Settle (default=quote)" value={clobForm.settle} onChange={(v) => setClobForm({ ...clobForm, settle: v })} placeholder="USDT" />
                  <div className="flex gap-3">
                    <FormField label="Price Precision" value={String(clobForm.price_precision)} onChange={(v) => setClobForm({ ...clobForm, price_precision: parseInt(v) || 8 })} type="number" />
                    <FormField label="Qty Precision" value={String(clobForm.quantity_precision)} onChange={(v) => setClobForm({ ...clobForm, quantity_precision: parseInt(v) || 8 })} type="number" />
                  </div>
                </div>
                <ModalActions saving={saving} onSave={handleCreateClob} onCancel={() => setModal(null)} label="Create" />
              </>
            )}

            {/* Create Pool */}
            {modal === 'create_pool' && (
              <>
                <h3 className="text-lg font-semibold text-text-primary mb-4">Create AMM Pool</h3>
                <div className="space-y-3">
                  <FormField label="Base Asset" value={poolForm.base_asset} onChange={(v) => setPoolForm({ ...poolForm, base_asset: v })} placeholder="VEGA" />
                  <FormField label="Quote Asset" value={poolForm.quote_asset} onChange={(v) => setPoolForm({ ...poolForm, quote_asset: v })} placeholder="USDT" />
                  <FormField label="Market" value={poolForm.market} onChange={(v) => setPoolForm({ ...poolForm, market: v })} placeholder="SPOT" />
                  <div className="flex gap-3">
                    <FormField label="Init Reserve Base" value={String(poolForm.initial_reserve_base)} onChange={(v) => setPoolForm({ ...poolForm, initial_reserve_base: parseFloat(v) || 0 })} type="number" />
                    <FormField label="Init Reserve Quote" value={String(poolForm.initial_reserve_quote)} onChange={(v) => setPoolForm({ ...poolForm, initial_reserve_quote: parseFloat(v) || 0 })} type="number" />
                  </div>
                  <FormField label="Fee Rate" value={String(poolForm.fee_rate)} onChange={(v) => setPoolForm({ ...poolForm, fee_rate: parseFloat(v) || 0.003 })} type="number" />
                </div>
                <ModalActions saving={saving} onSave={handleCreatePool} onCancel={() => setModal(null)} label="Create" />
              </>
            )}

            {/* Edit */}
            {modal === 'edit' && editTarget && (
              <>
                <h3 className="text-lg font-semibold text-text-primary mb-1">Edit Symbol</h3>
                <p className="text-sm text-text-tertiary mb-4 font-mono">{editTarget.symbol}</p>
                <div className="space-y-3">
                  <div className="flex gap-3">
                    <FormField label="Min Trade" value={String(editForm.min_trade_amount)} onChange={(v) => setEditForm({ ...editForm, min_trade_amount: parseFloat(v) || 0 })} type="number" />
                    <FormField label="Max Trade" value={String(editForm.max_trade_amount)} onChange={(v) => setEditForm({ ...editForm, max_trade_amount: parseFloat(v) || 0 })} type="number" />
                  </div>
                  <div className="flex gap-3">
                    <FormField label="Price Precision" value={String(editForm.price_precision)} onChange={(v) => setEditForm({ ...editForm, price_precision: parseInt(v) || 8 })} type="number" />
                    <FormField label="Qty Precision" value={String(editForm.quantity_precision)} onChange={(v) => setEditForm({ ...editForm, quantity_precision: parseInt(v) || 8 })} type="number" />
                  </div>
                  <FormField label="Fee Rate" value={String(editForm.fee_rate)} onChange={(v) => setEditForm({ ...editForm, fee_rate: parseFloat(v) || 0 })} type="number" />
                </div>
                <ModalActions saving={saving} onSave={handleEdit} onCancel={() => setModal(null)} label="Save" />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Reusable form components ──

function FormField({ label, value, onChange, placeholder, type = 'text' }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <div className="flex-1">
      <label className="block text-xs text-text-tertiary mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-bg-tertiary border border-border-default rounded-md text-sm text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue"
      />
    </div>
  )
}

function ModalActions({ saving, onSave, onCancel, label }: {
  saving: boolean
  onSave: () => void
  onCancel: () => void
  label: string
}) {
  return (
    <div className="flex gap-2 justify-end mt-6">
      <button onClick={onCancel} className="px-4 py-2 text-sm text-text-secondary border border-border-default rounded-md hover:border-border-hover">
        Cancel
      </button>
      <button onClick={onSave} disabled={saving} className="px-4 py-2 text-sm bg-accent-blue text-white rounded-md hover:bg-accent-blue/80 disabled:opacity-50">
        {saving ? 'Saving...' : label}
      </button>
    </div>
  )
}

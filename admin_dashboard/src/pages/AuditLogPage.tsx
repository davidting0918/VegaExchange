import { useEffect, useState, useCallback } from 'react'
import { AdminService } from '@/api/services/AdminService'

interface AuditEntry {
  id: number
  admin_id: string
  admin_name?: string
  admin_email?: string
  action: string
  target_type: string | null
  target_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

const PAGE_SIZE = 20

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)

  // Filters
  const [actionFilter, setActionFilter] = useState('')
  const [targetTypeFilter, setTargetTypeFilter] = useState('')

  const loadAuditLog = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { limit: PAGE_SIZE, offset }
      if (actionFilter) params.action = actionFilter
      if (targetTypeFilter) params.target_type = targetTypeFilter

      const res = await AdminService.getAuditLog(params as Parameters<typeof AdminService.getAuditLog>[0])
      if (res.success && res.data) {
        const data = res.data as { logs: AuditEntry[]; total: number }
        setEntries(data.logs || [])
        setTotal(data.total || 0)
      }
    } catch (err) {
      console.error('Failed to load audit log:', err)
    } finally {
      setLoading(false)
    }
  }, [offset, actionFilter, targetTypeFilter])

  useEffect(() => { loadAuditLog() }, [loadAuditLog])

  const handleFilter = () => {
    setOffset(0)
    loadAuditLog()
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div>
      <h2 className="text-lg font-semibold text-text-primary mb-1">Audit Log</h2>
      <p className="text-sm text-text-tertiary mb-6">History of all admin actions.</p>

      {/* Filters */}
      <div className="mb-4 flex gap-3 items-end">
        <div>
          <label className="block text-xs text-text-tertiary mb-1">Action</label>
          <input
            type="text"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="e.g. create_symbol"
            className="px-3 py-1.5 bg-bg-tertiary border border-border-default rounded-md text-sm text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue"
          />
        </div>
        <div>
          <label className="block text-xs text-text-tertiary mb-1">Target Type</label>
          <select
            value={targetTypeFilter}
            onChange={(e) => setTargetTypeFilter(e.target.value)}
            className="px-3 py-1.5 bg-bg-tertiary border border-border-default rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
          >
            <option value="">All</option>
            <option value="symbol">Symbol</option>
            <option value="pool">Pool</option>
            <option value="user">User</option>
            <option value="setting">Setting</option>
            <option value="whitelist">Whitelist</option>
          </select>
        </div>
        <button
          onClick={handleFilter}
          className="px-4 py-1.5 text-sm bg-accent-blue text-white rounded-md hover:bg-accent-blue/80"
        >
          Filter
        </button>
        {(actionFilter || targetTypeFilter) && (
          <button
            onClick={() => { setActionFilter(''); setTargetTypeFilter(''); setOffset(0) }}
            className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary border border-border-default rounded-md"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="border border-border-default rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default bg-bg-secondary">
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Admin</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Target</th>
              <th className="px-4 py-3 font-medium">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <div className="inline-block w-5 h-5 border-2 border-text-tertiary border-t-accent-blue rounded-full animate-spin" />
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-text-tertiary text-sm">
                  No audit log entries found.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id} className="text-sm">
                  <td className="px-4 py-3 text-text-tertiary text-xs whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {entry.admin_name || entry.admin_email || entry.admin_id}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 text-xs rounded bg-bg-hover text-text-primary">
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-text-secondary text-xs">
                    {entry.target_type && (
                      <span className="text-text-tertiary">{entry.target_type}:</span>
                    )}{' '}
                    {entry.target_id || '—'}
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    {entry.details ? (
                      <code className="text-xs text-text-tertiary break-all">
                        {JSON.stringify(entry.details)}
                      </code>
                    ) : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-text-secondary">
          <span>Page {currentPage} of {totalPages} ({total} entries)</span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              className="px-3 py-1 border border-border-default rounded-md hover:border-border-hover disabled:opacity-30"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= total}
              className="px-3 py-1 border border-border-default rounded-md hover:border-border-hover disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

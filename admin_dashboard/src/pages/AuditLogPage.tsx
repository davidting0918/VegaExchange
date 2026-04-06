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

// Summarize details into a short string for collapsed view
function summarizeDetails(details: Record<string, unknown> | null): string {
  if (!details) return '—'
  const keys = Object.keys(details)
  if (keys.length === 0) return '—'

  // Common patterns
  if ('old' in details && 'new' in details) {
    return `${keys.length - 2 > 0 ? keys.length + ' fields' : 'value'} changed`
  }
  if (keys.length <= 2) {
    return keys.map(k => `${k}: ${JSON.stringify(details[k])}`).join(', ')
  }
  return `${keys.length} fields`
}

// Render a value with appropriate formatting
function renderValue(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

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

  const toggleExpand = (id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
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
              <th className="px-4 py-3 font-medium w-8"></th>
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Admin</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Target</th>
              <th className="px-4 py-3 font-medium">Summary</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <div className="inline-block w-5 h-5 border-2 border-text-tertiary border-t-accent-blue rounded-full animate-spin" />
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-text-tertiary text-sm">
                  No audit log entries found.
                </td>
              </tr>
            ) : (
              entries.map((entry) => {
                const isExpanded = expandedIds.has(entry.id)
                const hasDetails = entry.details && Object.keys(entry.details).length > 0

                return (
                  <tr
                    key={entry.id}
                    className={`text-sm ${hasDetails ? 'cursor-pointer hover:bg-bg-tertiary/30' : ''}`}
                    onClick={() => hasDetails && toggleExpand(entry.id)}
                  >
                    <td colSpan={6} className="p-0">
                      {/* Row content */}
                      <div className="flex items-center px-4 py-3">
                        {/* Expand arrow */}
                        <div className="w-8 flex-shrink-0">
                          {hasDetails && (
                            <span className={`text-text-tertiary text-xs transition-transform inline-block ${isExpanded ? 'rotate-90' : ''}`}>
                              ▶
                            </span>
                          )}
                        </div>
                        {/* Time */}
                        <div className="w-40 flex-shrink-0 text-text-tertiary text-xs whitespace-nowrap">
                          {new Date(entry.created_at).toLocaleString()}
                        </div>
                        {/* Admin */}
                        <div className="w-32 flex-shrink-0 text-text-secondary truncate">
                          {entry.admin_name || entry.admin_email || entry.admin_id}
                        </div>
                        {/* Action */}
                        <div className="w-40 flex-shrink-0">
                          <span className="px-2 py-0.5 text-xs rounded bg-bg-hover text-text-primary">
                            {entry.action}
                          </span>
                        </div>
                        {/* Target */}
                        <div className="w-32 flex-shrink-0 text-text-secondary text-xs">
                          {entry.target_type && (
                            <span className="text-text-tertiary">{entry.target_type}:</span>
                          )}{' '}
                          {entry.target_id || '—'}
                        </div>
                        {/* Summary */}
                        <div className="flex-1 text-text-tertiary text-xs truncate">
                          {summarizeDetails(entry.details)}
                        </div>
                      </div>

                      {/* Expanded details */}
                      {isExpanded && entry.details && (
                        <div className="px-4 pb-4 pl-12">
                          <div className="bg-bg-tertiary rounded-md p-4 space-y-3">
                            {/* Check for old/new pattern */}
                            {'old' in entry.details && 'new' in entry.details ? (
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <p className="text-xs font-medium text-accent-red mb-2">Old Value</p>
                                  <pre className="text-xs font-mono text-text-secondary whitespace-pre-wrap bg-accent-red/5 rounded p-2 border border-accent-red/10">
                                    {renderValue(entry.details.old)}
                                  </pre>
                                </div>
                                <div>
                                  <p className="text-xs font-medium text-accent-green mb-2">New Value</p>
                                  <pre className="text-xs font-mono text-text-secondary whitespace-pre-wrap bg-accent-green/5 rounded p-2 border border-accent-green/10">
                                    {renderValue(entry.details.new)}
                                  </pre>
                                </div>
                                {/* Other fields besides old/new */}
                                {Object.entries(entry.details)
                                  .filter(([k]) => k !== 'old' && k !== 'new')
                                  .map(([key, val]) => (
                                    <div key={key} className="col-span-2">
                                      <span className="text-xs text-text-tertiary">{key}:</span>{' '}
                                      <span className="text-xs text-text-primary font-mono">{renderValue(val)}</span>
                                    </div>
                                  ))
                                }
                              </div>
                            ) : (
                              /* Generic key-value display */
                              <div className="space-y-1.5">
                                {Object.entries(entry.details).map(([key, val]) => (
                                  <div key={key} className="flex gap-3">
                                    <span className="text-xs text-text-tertiary min-w-[80px]">{key}:</span>
                                    <span className="text-xs text-text-primary font-mono break-all">
                                      {renderValue(val)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })
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

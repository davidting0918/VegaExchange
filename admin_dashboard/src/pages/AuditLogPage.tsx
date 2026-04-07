import { useEffect, useState, useCallback, useMemo } from 'react'
import { AdminService } from '@/api/services/AdminService'

type DetailsValue = Record<string, unknown> | unknown[] | string | number | boolean | null

interface AuditDetails {
  old: DetailsValue
  new: DetailsValue
}

interface AuditEntry {
  id: number
  admin_id: string
  admin_name?: string
  admin_email?: string
  action: string
  target_type: string | null
  target_id: string | null
  // Backend stores `details` as JSONB but asyncpg returns it as a raw JSON
  // string, so the API ships it as a string. We parse it on the client.
  details: AuditDetails | string | null
  created_at: string
}

const PAGE_SIZE = 20

// Parse JSON-encoded strings produced by asyncpg's default JSONB serialization.
// Returns the parsed value, or the raw input on parse failure / non-string input.
function parseJsonValue(raw: unknown): unknown {
  if (typeof raw !== 'string') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

// Normalize a raw `details` field into the typed AuditDetails shape, or null
// if the value is missing / unparseable / not a {old, new} object.
function normalizeDetails(raw: AuditDetails | string | null | undefined): AuditDetails | null {
  if (raw === null || raw === undefined) return null
  const parsed = parseJsonValue(raw)
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return null
  const obj = parsed as Record<string, unknown>
  if (!('old' in obj) && !('new' in obj)) return null
  return {
    old: (obj.old ?? null) as DetailsValue,
    new: (obj.new ?? null) as DetailsValue,
  }
}

// Pretty-print any JSON-serializable value with 2-space indent
function prettyJson(value: unknown): string {
  if (value === null || value === undefined) return ''
  return JSON.stringify(value, null, 2)
}

type DiffLineKind = 'unchanged' | 'removed' | 'added'
interface DiffLine {
  kind: DiffLineKind
  text: string
}

// LCS-based unified line diff (no external dependency)
function lineDiff(oldText: string, newText: string): DiffLine[] {
  const a = oldText.split('\n')
  const b = newText.split('\n')
  const m = a.length
  const n = b.length

  // dp[i][j] = LCS length of a[i..] and b[j..]
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const result: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      result.push({ kind: 'unchanged', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      result.push({ kind: 'removed', text: a[i] })
      i++
    } else {
      result.push({ kind: 'added', text: b[j] })
      j++
    }
  }
  while (i < m) result.push({ kind: 'removed', text: a[i++] })
  while (j < n) result.push({ kind: 'added', text: b[j++] })
  return result
}

// Build diff lines based on the {old, new} shape
function buildDiffLines(details: AuditDetails): DiffLine[] {
  const { old: oldVal, new: newVal } = details

  // CREATE: only new -> entire new rendered as added
  if (oldVal === null || oldVal === undefined) {
    return prettyJson(newVal)
      .split('\n')
      .map((text) => ({ kind: 'added' as const, text }))
  }

  // DELETE: only old -> entire old rendered as removed
  if (newVal === null || newVal === undefined) {
    return prettyJson(oldVal)
      .split('\n')
      .map((text) => ({ kind: 'removed' as const, text }))
  }

  // UPDATE: line diff between pretty-printed old and new
  return lineDiff(prettyJson(oldVal), prettyJson(newVal))
}

function DetailsDiffPanel({ details }: { details: AuditDetails }) {
  const lines = useMemo(() => buildDiffLines(details), [details])

  return (
    <div className="bg-bg-tertiary rounded-md border border-border-default overflow-hidden">
      <pre className="font-mono text-xs leading-5 m-0">
        {lines.map((line, idx) => {
          const prefix = line.kind === 'added' ? '+ ' : line.kind === 'removed' ? '- ' : '  '
          const className =
            line.kind === 'added'
              ? 'bg-accent-green/10 text-accent-green'
              : line.kind === 'removed'
                ? 'bg-accent-red/10 text-accent-red'
                : 'text-text-tertiary'
          return (
            <div key={idx} className={`px-3 ${className}`}>
              <span className="select-none opacity-60">{prefix}</span>
              {line.text || '\u00A0'}
            </div>
          )
        })}
      </pre>
    </div>
  )
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

  useEffect(() => {
    loadAuditLog()
  }, [loadAuditLog])

  const handleFilter = () => {
    setOffset(0)
    loadAuditLog()
  }

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
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
            onClick={() => {
              setActionFilter('')
              setTargetTypeFilter('')
              setOffset(0)
            }}
            className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary border border-border-default rounded-md"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="border border-border-default rounded-lg overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup>
            <col className="w-10" />
            <col className="w-48" />
            <col className="w-40" />
            <col className="w-56" />
            <col />
          </colgroup>
          <thead>
            <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default bg-bg-secondary">
              <th className="px-4 py-3 font-medium"></th>
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Admin</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Target</th>
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
              entries.map((entry) => {
                const isExpanded = expandedIds.has(entry.id)
                const details = normalizeDetails(entry.details)
                const hasDetails = details !== null

                return [
                  <tr
                    key={`row-${entry.id}`}
                    className={`text-sm ${hasDetails ? 'cursor-pointer hover:bg-bg-tertiary/40' : ''}`}
                    onClick={() => hasDetails && toggleExpand(entry.id)}
                  >
                    <td className="px-4 py-3 align-middle">
                      {hasDetails && (
                        <span
                          className={`inline-block text-text-tertiary text-xs transition-transform ${
                            isExpanded ? 'rotate-90' : ''
                          }`}
                        >
                          ▶
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 align-middle text-text-tertiary text-xs whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 align-middle text-text-secondary truncate">
                      {entry.admin_name || entry.admin_email || entry.admin_id}
                    </td>
                    <td className="px-4 py-3 align-middle">
                      <span className="px-2 py-0.5 text-xs rounded bg-bg-hover text-text-primary font-mono">
                        {entry.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-middle text-text-secondary text-xs truncate">
                      {entry.target_type && (
                        <span className="text-text-tertiary">{entry.target_type}: </span>
                      )}
                      {entry.target_id || '—'}
                    </td>
                  </tr>,
                  isExpanded && details ? (
                    <tr key={`detail-${entry.id}`} className="bg-bg-secondary/40">
                      <td colSpan={5} className="px-4 py-3 pl-14">
                        <DetailsDiffPanel details={details} />
                      </td>
                    </tr>
                  ) : null,
                ]
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-text-secondary">
          <span>
            Page {currentPage} of {totalPages} ({total} entries)
          </span>
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

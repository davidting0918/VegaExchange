import { useEffect, useState, useCallback } from 'react'
import { AdminService } from '@/api/services/AdminService'

interface WhitelistEntry {
  id: number
  email: string
  description: string | null
  created_at: string
}

export function WhitelistPage() {
  const [entries, setEntries] = useState<WhitelistEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [newEmail, setNewEmail] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [adding, setAdding] = useState(false)
  const [removingId, setRemovingId] = useState<number | null>(null)
  const [confirmRemoveId, setConfirmRemoveId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const loadWhitelist = useCallback(async () => {
    try {
      const res = await AdminService.getWhitelist()
      if (res.success && res.data) setEntries(res.data as WhitelistEntry[])
    } catch (err) {
      console.error('Failed to load whitelist:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadWhitelist() }, [loadWhitelist])

  const handleAdd = async () => {
    if (!newEmail.trim()) return
    setAdding(true)
    setMessage(null)
    try {
      const res = await AdminService.addWhitelist(newEmail.trim(), newDesc.trim() || undefined)
      if (res.success) {
        setMessage({ text: `Added ${newEmail} to whitelist.`, type: 'success' })
        setNewEmail('')
        setNewDesc('')
        loadWhitelist()
      }
    } catch (err) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setMessage({ text: axiosErr.response?.data?.detail || 'Failed to add email', type: 'error' })
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id: number) => {
    if (confirmRemoveId !== id) {
      setConfirmRemoveId(id)
      return
    }
    setRemovingId(id)
    setMessage(null)
    try {
      const res = await AdminService.removeWhitelist(id)
      if (res.success) {
        setMessage({ text: 'Email removed from whitelist.', type: 'success' })
        setConfirmRemoveId(null)
        loadWhitelist()
      }
    } catch (err) {
      console.error('Failed to remove:', err)
      setMessage({ text: 'Failed to remove email', type: 'error' })
    } finally {
      setRemovingId(null)
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
      <h2 className="text-lg font-semibold text-text-primary mb-1">Admin Whitelist</h2>
      <p className="text-sm text-text-tertiary mb-6">Only whitelisted emails can sign in to the admin dashboard.</p>

      {message && (
        <div className={`mb-4 p-3 text-sm rounded-lg ${
          message.type === 'success'
            ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
            : 'bg-accent-red/10 text-accent-red border border-accent-red/20'
        }`}>
          {message.text}
        </div>
      )}

      {/* Add form */}
      <div className="mb-6 p-4 border border-border-default rounded-lg bg-bg-secondary">
        <h3 className="text-sm font-medium text-text-primary mb-3">Add Email</h3>
        <div className="flex gap-3">
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="admin@example.com"
            className="flex-1 px-3 py-2 bg-bg-tertiary border border-border-default rounded-md text-sm text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue"
          />
          <input
            type="text"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Description (optional)"
            className="flex-1 px-3 py-2 bg-bg-tertiary border border-border-default rounded-md text-sm text-text-primary placeholder-text-tertiary focus:outline-none focus:border-accent-blue"
          />
          <button
            onClick={handleAdd}
            disabled={adding || !newEmail.trim()}
            className="px-4 py-2 text-sm bg-accent-blue text-white rounded-md hover:bg-accent-blue/80 disabled:opacity-50"
          >
            {adding ? 'Adding...' : 'Add'}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="border border-border-default rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default bg-bg-secondary">
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="px-4 py-3 font-medium">Added</th>
              <th className="px-4 py-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {entries.map((entry) => (
              <tr key={entry.id} className="text-sm">
                <td className="px-4 py-3 text-text-primary">{entry.email}</td>
                <td className="px-4 py-3 text-text-secondary">{entry.description || '—'}</td>
                <td className="px-4 py-3 text-text-tertiary text-xs">
                  {new Date(entry.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleRemove(entry.id)}
                    disabled={removingId === entry.id}
                    className={`px-3 py-1 text-xs rounded-md border ${
                      confirmRemoveId === entry.id
                        ? 'bg-accent-red/10 text-accent-red border-accent-red/20'
                        : 'text-text-secondary hover:text-text-primary border-border-default hover:border-border-hover'
                    } disabled:opacity-50`}
                  >
                    {removingId === entry.id ? 'Removing...' : confirmRemoveId === entry.id ? 'Confirm Remove' : 'Remove'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {entries.length === 0 && (
          <div className="text-center py-8 text-text-tertiary text-sm">No whitelist entries. Add one above.</div>
        )}
      </div>
    </div>
  )
}

import { useEffect, useState, useCallback } from 'react'
import { AdminService } from '@/api/services/AdminService'

interface Setting {
  key: string
  value: unknown
  description: string | null
  updated_at: string
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([])
  const [loading, setLoading] = useState(true)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const loadSettings = useCallback(async () => {
    try {
      const res = await AdminService.getSettings()
      if (res.success && res.data) setSettings(res.data as Setting[])
    } catch (err) {
      console.error('Failed to load settings:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadSettings() }, [loadSettings])

  const handleEdit = (setting: Setting) => {
    setEditingKey(setting.key)
    setEditValue(JSON.stringify(setting.value, null, 2))
    setMessage(null)
  }

  const handleCancel = () => {
    setEditingKey(null)
    setEditValue('')
  }

  const handleSave = async (key: string) => {
    setSaving(true)
    setMessage(null)
    try {
      const parsed = JSON.parse(editValue)
      const res = await AdminService.updateSetting(key, parsed)
      if (res.success) {
        setMessage({ text: `Setting "${key}" updated successfully.`, type: 'success' })
        setEditingKey(null)
        loadSettings()
      }
    } catch (err) {
      const msg = err instanceof SyntaxError ? 'Invalid JSON format' : 'Failed to update setting'
      setMessage({ text: msg, type: 'error' })
    } finally {
      setSaving(false)
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
      <h2 className="text-lg font-semibold text-text-primary mb-1">Settings</h2>
      <p className="text-sm text-text-tertiary mb-6">Platform-wide configuration values.</p>

      {message && (
        <div className={`mb-4 p-3 text-sm rounded-lg ${
          message.type === 'success'
            ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
            : 'bg-accent-red/10 text-accent-red border border-accent-red/20'
        }`}>
          {message.text}
        </div>
      )}

      <div className="border border-border-default rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-text-tertiary uppercase tracking-wide border-b border-border-default bg-bg-secondary">
              <th className="px-4 py-3 font-medium">Key</th>
              <th className="px-4 py-3 font-medium">Value</th>
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="px-4 py-3 font-medium">Updated</th>
              <th className="px-4 py-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {settings.map((s) => (
              <tr key={s.key} className="text-sm">
                <td className="px-4 py-3 font-mono text-text-primary">{s.key}</td>
                <td className="px-4 py-3 max-w-xs">
                  {editingKey === s.key ? (
                    <textarea
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      rows={4}
                      className="w-full px-3 py-2 bg-bg-tertiary border border-border-default rounded-md text-text-primary font-mono text-xs focus:outline-none focus:border-accent-blue"
                    />
                  ) : (
                    <code className="text-xs text-text-secondary break-all">
                      {JSON.stringify(s.value)}
                    </code>
                  )}
                </td>
                <td className="px-4 py-3 text-text-secondary">{s.description || '—'}</td>
                <td className="px-4 py-3 text-text-tertiary text-xs">
                  {new Date(s.updated_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right">
                  {editingKey === s.key ? (
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => handleSave(s.key)}
                        disabled={saving}
                        className="px-3 py-1 text-xs bg-accent-blue text-white rounded-md hover:bg-accent-blue/80 disabled:opacity-50"
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={handleCancel}
                        className="px-3 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-default rounded-md"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleEdit(s)}
                      className="px-3 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-default rounded-md hover:border-border-hover"
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {settings.length === 0 && (
          <div className="text-center py-8 text-text-tertiary text-sm">No settings found.</div>
        )}
      </div>
    </div>
  )
}

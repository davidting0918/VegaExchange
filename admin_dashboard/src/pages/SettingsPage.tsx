import { useEffect, useState, useCallback, useMemo } from 'react'
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

  // JSON validation
  const jsonError = useMemo(() => {
    if (!editValue) return null
    try {
      JSON.parse(editValue)
      return null
    } catch (e) {
      return (e as Error).message
    }
  }, [editValue])

  const handleEdit = (setting: Setting) => {
    setEditingKey(setting.key)
    setEditValue(JSON.stringify(setting.value, null, 2))
    setMessage(null)
  }

  const handleCancel = () => {
    setEditingKey(null)
    setEditValue('')
  }

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(editValue)
      setEditValue(JSON.stringify(parsed, null, 2))
    } catch {
      // Can't format invalid JSON
    }
  }

  const handleSave = async (key: string) => {
    if (jsonError) return
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

  // Count lines for line numbers
  const lineCount = editValue.split('\n').length

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

      <div className="space-y-4">
        {settings.map((s) => (
          <div key={s.key} className="border border-border-default rounded-lg overflow-hidden">
            {/* Setting header */}
            <div className="flex items-center justify-between px-4 py-3 bg-bg-secondary">
              <div>
                <span className="font-mono text-sm text-text-primary font-medium">{s.key}</span>
                {s.description && (
                  <p className="text-xs text-text-tertiary mt-0.5">{s.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-text-tertiary">
                  {new Date(s.updated_at).toLocaleString()}
                </span>
                {editingKey !== s.key && (
                  <button
                    onClick={() => handleEdit(s)}
                    className="px-3 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-default rounded-md hover:border-border-hover"
                  >
                    Edit
                  </button>
                )}
              </div>
            </div>

            {/* Value display / editor */}
            <div className="px-4 py-3">
              {editingKey === s.key ? (
                <div>
                  {/* Editor with line numbers */}
                  <div className={`flex rounded-md border overflow-hidden ${
                    jsonError ? 'border-accent-red' : 'border-border-default focus-within:border-accent-blue'
                  }`}>
                    {/* Line numbers */}
                    <div className="bg-bg-tertiary px-2 py-3 text-right select-none border-r border-border-default">
                      {Array.from({ length: lineCount }, (_, i) => (
                        <div key={i} className="text-xs text-text-tertiary font-mono leading-5">
                          {i + 1}
                        </div>
                      ))}
                    </div>
                    {/* Textarea */}
                    <textarea
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      rows={Math.max(lineCount, 4)}
                      spellCheck={false}
                      className="flex-1 px-3 py-3 bg-bg-primary text-text-primary font-mono text-xs leading-5 resize-none focus:outline-none"
                    />
                  </div>

                  {/* Validation error */}
                  {jsonError && (
                    <div className="mt-2 px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-md">
                      <p className="text-xs text-accent-red font-mono">{jsonError}</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center justify-between mt-3">
                    <button
                      onClick={handleFormat}
                      className="text-xs text-text-tertiary hover:text-accent-blue"
                    >
                      Format JSON
                    </button>
                    <div className="flex gap-2">
                      <button
                        onClick={handleCancel}
                        className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary border border-border-default rounded-md"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSave(s.key)}
                        disabled={saving || !!jsonError}
                        className="px-4 py-1.5 text-xs bg-accent-blue text-white rounded-md hover:bg-accent-blue/80 disabled:opacity-40"
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* Read-only pretty display */
                <pre className="text-xs text-text-secondary font-mono whitespace-pre-wrap leading-5">
                  {JSON.stringify(s.value, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}

        {settings.length === 0 && (
          <div className="text-center py-8 text-text-tertiary text-sm border border-border-default rounded-lg">
            No settings found.
          </div>
        )}
      </div>
    </div>
  )
}

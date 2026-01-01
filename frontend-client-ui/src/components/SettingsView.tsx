import { useState, useEffect } from 'react'
import LoggingView from './LoggingView'
import FetchesView from './FetchesView'
import FetchQueueView from './FetchQueueView'
import DataView from './DataView'
import './SettingsView.css'

const API_BASE = '/api'

type SettingsTab = 'settings' | 'fetch-queue' | 'fetches' | 'data' | 'logs'

interface SettingField {
  key: string
  label: string
  type: 'text' | 'password'
  placeholder: string
  description: string
}

const SETTINGS_FIELDS: SettingField[] = [
  {
    key: 'community_ids',
    label: 'Community IDs',
    type: 'text',
    placeholder: 'e.g. my-community, another-community',
    description: 'Comma-separated list of Skool communities to monitor.'
  },
  {
    key: 'openai_api_key',
    label: 'OpenAI API Key',
    type: 'password',
    placeholder: 'sk-...',
    description: 'API key for OpenAI integration (optional, for AI analysis).'
  }
]

function GeneralSettings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadSettings = async () => {
      setLoading(true)
      const loaded: Record<string, string> = {}

      for (const field of SETTINGS_FIELDS) {
        try {
          const res = await fetch(`${API_BASE}/setting?key=${field.key}`)
          if (res.ok) {
            const data = await res.json()
            loaded[field.key] = data.value || ''
          }
        } catch (err) {
          console.error(`Failed to load setting ${field.key}:`, err)
        }
      }

      setSettings(loaded)
      setLoading(false)
    }

    loadSettings()
  }, [])

  const saveSetting = async (key: string) => {
    setSaving(key)
    setSaveSuccess(null)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value: settings[key] || '' })
      })

      if (!res.ok) throw new Error('Failed to save setting')

      setSaveSuccess(key)
      setTimeout(() => setSaveSuccess(null), 2000)
    } catch (err) {
      setError(`Error saving "${key}"`)
    } finally {
      setSaving(null)
    }
  }

  const updateSetting = (key: string, value: string) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  if (loading) {
    return <p>Loading settings...</p>
  }

  return (
    <div className="general-settings">
      <h3>General Settings</h3>
      <p>Configure your CatKnows instance</p>

      {error && <p className="error">{error}</p>}

      {SETTINGS_FIELDS.map(field => (
        <fieldset key={field.key}>
          <legend>{field.label}</legend>
          <div className="setting-row">
            <input
              id={field.key}
              type={field.type}
              value={settings[field.key] || ''}
              onChange={(e) => updateSetting(field.key, e.target.value)}
              placeholder={field.placeholder}
            />
            <button
              onClick={() => saveSetting(field.key)}
              disabled={saving === field.key}
            >
              {saving === field.key ? 'Saving...' : saveSuccess === field.key ? 'Saved!' : 'Save'}
            </button>
          </div>
          <p className="description">{field.description}</p>
        </fieldset>
      ))}

      <fieldset>
        <legend>Notes</legend>
        <ul>
          <li><strong>Community IDs:</strong> The browser extension uses these IDs to generate the fetch queue.</li>
          <li><strong>OpenAI API Key:</strong> Required for AI-powered analysis. The key is stored locally and never sent to our servers.</li>
        </ul>
      </fieldset>
    </div>
  )
}

export function SettingsView() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('settings')

  return (
    <div className="settings-view">
      <div className="settings-tabs">
        <button
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button
          className={activeTab === 'fetch-queue' ? 'active' : ''}
          onClick={() => setActiveTab('fetch-queue')}
        >
          Fetch Queue
        </button>
        <button
          className={activeTab === 'fetches' ? 'active' : ''}
          onClick={() => setActiveTab('fetches')}
        >
          Fetches
        </button>
        <button
          className={activeTab === 'data' ? 'active' : ''}
          onClick={() => setActiveTab('data')}
        >
          Data View
        </button>
        <button
          className={activeTab === 'logs' ? 'active' : ''}
          onClick={() => setActiveTab('logs')}
        >
          Logs
        </button>
      </div>

      <div className="settings-content">
        {activeTab === 'settings' && <GeneralSettings />}
        {activeTab === 'fetch-queue' && <FetchQueueView />}
        {activeTab === 'fetches' && <FetchesView />}
        {activeTab === 'data' && <DataView />}
        {activeTab === 'logs' && <LoggingView />}
      </div>
    </div>
  )
}

export default SettingsView

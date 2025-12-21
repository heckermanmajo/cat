import { useState, useCallback, useEffect } from 'react'
import './FetchQueueView.css'

interface FetchTask {
  id: string
  type: string
  priority: number
  communityId?: string
  entityId?: string
  page?: number
  params?: Record<string, unknown>
  reason: string
  lastFetchedAt?: string
}

interface FetchQueue {
  tasks: FetchTask[]
  generatedAt: string
  totalTasks: number
}

const API_BASE = '/api'

const PRIORITY_LABELS: Record<number, string> = {
  1: 'High',
  2: 'Medium',
  3: 'Low'
}

export function FetchQueueView() {
  const [queue, setQueue] = useState<FetchQueue | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [communityIds, setCommunityIds] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    const loadCommunityIds = async () => {
      try {
        const res = await fetch(`${API_BASE}/setting?key=community_ids`)
        if (res.ok) {
          const data = await res.json()
          if (data.value) {
            setCommunityIds(data.value)
          }
        }
      } catch (err) {
        console.error('Failed to load community_ids setting:', err)
      }
    }
    loadCommunityIds()
  }, [])

  const saveCommunityIds = async () => {
    setSaving(true)
    setSaveSuccess(false)
    try {
      const res = await fetch(`${API_BASE}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'community_ids', value: communityIds.trim() })
      })
      if (!res.ok) throw new Error('Failed to save')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (err) {
      setError('Error saving community IDs')
    } finally {
      setSaving(false)
    }
  }

  const fetchQueue = useCallback(async () => {
    if (!communityIds.trim()) {
      setError('Please enter community IDs')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      params.append('communityIds', communityIds.trim())

      const res = await fetch(`${API_BASE}/fetch-queue?${params}`)
      if (!res.ok) throw new Error('Failed to fetch queue')
      const data: FetchQueue = await res.json()
      setQueue(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [communityIds])

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  const getTaskStats = () => {
    if (!queue) return {}
    return queue.tasks.reduce((acc, task) => {
      acc[task.type] = (acc[task.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }

  const stats = getTaskStats()

  return (
    <div className="fetch-queue-view">
      <h2>Fetch Queue</h2>
      <p className="subtitle">Manage fetch tasks for the browser extension</p>

      <fieldset>
        <legend>Community IDs</legend>
        <div className="input-row">
          <input
            type="text"
            value={communityIds}
            onChange={(e) => setCommunityIds(e.target.value)}
            placeholder="e.g. my-community, another-community"
          />
          <button onClick={saveCommunityIds} disabled={saving}>
            {saving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save'}
          </button>
          <button onClick={fetchQueue} disabled={loading}>
            {loading ? 'Loading...' : 'Generate Queue'}
          </button>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}

      {queue && (
        <>
          <fieldset>
            <legend>Statistics</legend>
            <p><strong>Total Tasks:</strong> {queue.totalTasks}</p>
            <p><strong>Generated:</strong> {formatDate(queue.generatedAt)}</p>
            {Object.entries(stats).length > 0 && (
              <p>
                <strong>By Type:</strong>{' '}
                {Object.entries(stats).map(([type, count]) => `${type}: ${count}`).join(', ')}
              </p>
            )}
          </fieldset>

          {queue.tasks.length === 0 ? (
            <p>No fetch tasks in queue. All data is up to date!</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Type</th>
                  <th>Priority</th>
                  <th>Community</th>
                  <th>Entity</th>
                  <th>Reason</th>
                  <th>Last Fetched</th>
                </tr>
              </thead>
              <tbody>
                {queue.tasks.map((task, index) => (
                  <tr key={task.id}>
                    <td>{index + 1}</td>
                    <td>{task.type}</td>
                    <td>{PRIORITY_LABELS[task.priority] || `P${task.priority}`}</td>
                    <td>{task.communityId || '-'}</td>
                    <td>{task.entityId || (task.page ? `Page ${task.page}` : '-')}</td>
                    <td>{task.reason}</td>
                    <td>{task.lastFetchedAt ? formatDate(task.lastFetchedAt) : 'Never'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {!queue && !loading && !error && (
        <p>Enter community IDs and click "Generate Queue" to see pending fetch tasks.</p>
      )}
    </div>
  )
}

export default FetchQueueView

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

interface FetchQueueOptions {
  fetchPostLikes: boolean
  fetchPostComments: boolean
  fetchMemberProfiles: boolean
  fetchSharedCommunities: boolean
  minSharedMembersForFetch: number
  refreshIntervalHours: number
  maxTasksPerType: number
}

interface FetchQueue {
  tasks: FetchTask[]
  generatedAt: string
  totalTasks: number
  usedOptions?: FetchQueueOptions
}

const API_BASE = '/api'

const PRIORITY_LABELS: Record<number, string> = {
  0: 'Critical',
  1: 'High',
  2: 'Medium',
  3: 'Low',
  4: 'Lowest'
}

const PRIORITY_COLORS: Record<number, string> = {
  0: '#dc2626',
  1: '#ea580c',
  2: '#ca8a04',
  3: '#16a34a',
  4: '#6b7280'
}

const DEFAULT_OPTIONS: FetchQueueOptions = {
  fetchPostLikes: true,
  fetchPostComments: true,
  fetchMemberProfiles: true,
  fetchSharedCommunities: true,
  minSharedMembersForFetch: 3,
  refreshIntervalHours: 24,
  maxTasksPerType: 0
}

export function FetchQueueView() {
  const [queue, setQueue] = useState<FetchQueue | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [communityIds, setCommunityIds] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Options State
  const [optionsExpanded, setOptionsExpanded] = useState(false)
  const [options, setOptions] = useState<FetchQueueOptions>(DEFAULT_OPTIONS)

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

  // Update options from queue response
  useEffect(() => {
    if (queue?.usedOptions) {
      setOptions(queue.usedOptions)
    }
  }, [queue?.usedOptions])

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

      // Add options to query params
      params.append('fetchPostLikes', String(options.fetchPostLikes))
      params.append('fetchPostComments', String(options.fetchPostComments))
      params.append('fetchMemberProfiles', String(options.fetchMemberProfiles))
      params.append('fetchSharedCommunities', String(options.fetchSharedCommunities))
      params.append('minSharedMembersForFetch', String(options.minSharedMembersForFetch))
      params.append('refreshIntervalHours', String(options.refreshIntervalHours))
      params.append('maxTasksPerType', String(options.maxTasksPerType))

      const res = await fetch(`${API_BASE}/fetch-queue?${params}`)
      if (!res.ok) throw new Error('Failed to fetch queue')
      const data: FetchQueue = await res.json()
      setQueue(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [communityIds, options])

  const resetOptions = () => {
    setOptions(DEFAULT_OPTIONS)
  }

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

  const getPriorityStats = () => {
    if (!queue) return {}
    return queue.tasks.reduce((acc, task) => {
      const label = PRIORITY_LABELS[task.priority] || `P${task.priority}`
      acc[label] = (acc[label] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }

  const stats = getTaskStats()
  const priorityStats = getPriorityStats()

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
          <button onClick={fetchQueue} disabled={loading} className="primary">
            {loading ? 'Loading...' : 'Generate Queue'}
          </button>
        </div>
      </fieldset>

      {/* Collapsible Options Panel */}
      <fieldset className="options-fieldset">
        <legend
          onClick={() => setOptionsExpanded(!optionsExpanded)}
          className="clickable-legend"
        >
          <span className={`toggle-icon ${optionsExpanded ? 'expanded' : ''}`}>▶</span>
          Fetch Options
          {!optionsExpanded && (
            <span className="options-summary">
              (Likes: {options.fetchPostLikes ? '✓' : '✗'},
              Comments: {options.fetchPostComments ? '✓' : '✗'},
              Profiles: {options.fetchMemberProfiles ? '✓' : '✗'},
              Shared: {options.fetchSharedCommunities ? '✓' : '✗'})
            </span>
          )}
        </legend>

        {optionsExpanded && (
          <div className="options-content">
            <div className="options-grid">
              {/* Boolean Options */}
              <div className="option-group">
                <h4>What to Fetch</h4>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={options.fetchPostLikes}
                    onChange={(e) => setOptions({...options, fetchPostLikes: e.target.checked})}
                  />
                  <span>Fetch Post Likes</span>
                  <small>Who liked each post</small>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={options.fetchPostComments}
                    onChange={(e) => setOptions({...options, fetchPostComments: e.target.checked})}
                  />
                  <span>Fetch Post Comments</span>
                  <small>Comments on each post (via post_details)</small>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={options.fetchMemberProfiles}
                    onChange={(e) => setOptions({...options, fetchMemberProfiles: e.target.checked})}
                  />
                  <span>Fetch Member Profiles</span>
                  <small>Full profile for each member</small>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={options.fetchSharedCommunities}
                    onChange={(e) => setOptions({...options, fetchSharedCommunities: e.target.checked})}
                  />
                  <span>Analyze Shared Communities</span>
                  <small>Find communities where many members overlap</small>
                </label>
              </div>

              {/* Numeric Options */}
              <div className="option-group">
                <h4>Configuration</h4>

                <label className="number-label">
                  <span>Min Shared Members for Fetch</span>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={options.minSharedMembersForFetch}
                    onChange={(e) => setOptions({...options, minSharedMembersForFetch: parseInt(e.target.value) || 3})}
                  />
                  <small>Only fetch communities with at least this many shared members</small>
                </label>

                <label className="number-label">
                  <span>Refresh Interval (hours)</span>
                  <input
                    type="number"
                    min="1"
                    max="168"
                    value={options.refreshIntervalHours}
                    onChange={(e) => setOptions({...options, refreshIntervalHours: parseInt(e.target.value) || 24})}
                  />
                  <small>How often to refresh already-fetched data</small>
                </label>

                <label className="number-label">
                  <span>Max Tasks per Type</span>
                  <input
                    type="number"
                    min="0"
                    max="1000"
                    value={options.maxTasksPerType}
                    onChange={(e) => setOptions({...options, maxTasksPerType: parseInt(e.target.value) || 0})}
                  />
                  <small>0 = unlimited</small>
                </label>
              </div>
            </div>

            <div className="options-actions">
              <button onClick={resetOptions} className="secondary">
                Reset to Defaults
              </button>
              <button onClick={fetchQueue} disabled={loading} className="primary">
                {loading ? 'Loading...' : 'Regenerate Queue'}
              </button>
            </div>
          </div>
        )}
      </fieldset>

      {error && <p className="error">{error}</p>}

      {queue && (
        <>
          <fieldset>
            <legend>Statistics</legend>
            <div className="stats-grid">
              <div className="stat-item">
                <strong>Total Tasks:</strong> {queue.totalTasks}
              </div>
              <div className="stat-item">
                <strong>Generated:</strong> {formatDate(queue.generatedAt)}
              </div>
            </div>

            {Object.entries(stats).length > 0 && (
              <div className="stats-breakdown">
                <strong>By Type:</strong>
                <div className="stats-chips">
                  {Object.entries(stats).map(([type, count]) => (
                    <span key={type} className="stat-chip type-chip">{type}: {count}</span>
                  ))}
                </div>
              </div>
            )}

            {Object.entries(priorityStats).length > 0 && (
              <div className="stats-breakdown">
                <strong>By Priority:</strong>
                <div className="stats-chips">
                  {Object.entries(priorityStats).map(([priority, count]) => (
                    <span
                      key={priority}
                      className="stat-chip priority-chip"
                      style={{
                        backgroundColor: PRIORITY_COLORS[
                          Object.entries(PRIORITY_LABELS).find(([, label]) => label === priority)?.[0] as unknown as number
                        ] || '#6b7280'
                      }}
                    >
                      {priority}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </fieldset>

          {queue.tasks.length === 0 ? (
            <p className="no-tasks">No fetch tasks in queue. All data is up to date!</p>
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
                    <td><code>{task.type}</code></td>
                    <td>
                      <span
                        className="priority-badge"
                        style={{ backgroundColor: PRIORITY_COLORS[task.priority] || '#6b7280' }}
                      >
                        {PRIORITY_LABELS[task.priority] || `P${task.priority}`}
                      </span>
                    </td>
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
        <p className="hint">Enter community IDs and click "Generate Queue" to see pending fetch tasks.</p>
      )}
    </div>
  )
}

export default FetchQueueView

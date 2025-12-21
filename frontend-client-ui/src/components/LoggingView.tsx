import { useState, useEffect, useCallback } from 'react'
import './LoggingView.css'

interface LogEntry {
  id: number
  level: string
  source: string
  message: string
  details?: string
  createdAt: string
}

interface LogsResponse {
  logs: LogEntry[]
  total: number
  sources: string[]
}

const API_BASE = '/api'

export function LoggingView() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [levelFilter, setLevelFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [limit, setLimit] = useState(50)

  const [expandedId, setExpandedId] = useState<number | null>(null)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError(null)

    const params = new URLSearchParams()
    if (levelFilter) params.append('level', levelFilter)
    if (sourceFilter) params.append('source', sourceFilter)
    params.append('limit', String(limit))

    try {
      const res = await fetch(`${API_BASE}/logs?${params}`)
      if (!res.ok) throw new Error('Failed to fetch logs')
      const data: LogsResponse = await res.json()
      setLogs(data.logs || [])
      setTotal(data.total)
      setSources(data.sources || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [levelFilter, sourceFilter, limit])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const clearLogs = async () => {
    if (!confirm('Delete all logs?')) return
    try {
      const res = await fetch(`${API_BASE}/logs`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to clear logs')
      fetchLogs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  return (
    <div className="logging-view">
      <h2>Logs</h2>
      <p>Total: {total}</p>

      <fieldset>
        <legend>Filters</legend>
        <div className="filter-row">
          <label>
            Level:
            <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
              <option value="">All</option>
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
            </select>
          </label>

          <label>
            Source:
            <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
              <option value="">All</option>
              {sources.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>

          <label>
            Limit:
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
            </select>
          </label>

          <button onClick={fetchLogs} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button onClick={clearLogs} disabled={loading}>
            Clear Logs
          </button>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Level</th>
            <th>Source</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {logs.length === 0 ? (
            <tr>
              <td colSpan={4}>No logs found</td>
            </tr>
          ) : (
            logs.map((log) => (
              <>
                <tr
                  key={log.id}
                  className={log.details ? 'clickable' : ''}
                  onClick={() => log.details && setExpandedId(expandedId === log.id ? null : log.id)}
                >
                  <td>{formatDate(log.createdAt)}</td>
                  <td className={`level-${log.level}`}>{log.level.toUpperCase()}</td>
                  <td>{log.source}</td>
                  <td>{log.message}</td>
                </tr>
                {expandedId === log.id && log.details && (
                  <tr key={`${log.id}-details`}>
                    <td colSpan={4}>
                      <pre>{log.details}</pre>
                    </td>
                  </tr>
                )}
              </>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export default LoggingView

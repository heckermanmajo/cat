import { useState, useEffect, useCallback } from 'react'
import './FetchesView.css'

interface FetchEntry {
  entityType: string
  entityId: string
  rawJson: string
  source: string
  fetchedAt: string
}

interface FetchesResponse {
  fetches: FetchEntry[]
  total: number
  entityTypes: string[]
  sources: string[]
}

const API_BASE = '/api'

const QUEUE_LOGIC_INFO = `
The fetch queue is dynamically generated based on the current data state:

1. FETCH TYPES & PRIORITIES:
   ┌─────────────────────┬──────────────────────────────────────────────────┐
   │ about_page          │ HIGH (never fetched) / MEDIUM (refresh due)     │
   │ members             │ HIGH (Page 1 missing) / MEDIUM (more pages)     │
   │ community_page      │ HIGH (missing) / MEDIUM (refresh)               │
   │ post_details        │ MEDIUM (missing) / LOW (refresh)                │
   │ profile             │ LOW (for known members)                         │
   │ likes               │ LOW (for known posts)                           │
   └─────────────────────┴──────────────────────────────────────────────────┘

2. GENERATION LOGIC (per community):
   ① Check About Page → missing or older than 24h?
   ② Check Members Pages → Page 1 present? More pages needed?
   ③ Check Community Page (Posts) → overview up to date?
   ④ Profiles for known members → extracted from members data
   ⑤ Post details for known posts → extracted from community page
   ⑥ Likes for posts → optional, if enabled

3. PRIORITY SORTING:
   1 = HIGH (critical, never fetched)
   2 = MEDIUM (important, refresh or new pages)
   3 = LOW (supplementary, profiles/likes)

4. LIMITS:
   • Refresh interval: 24 hours
   • Max tasks per type: 10
   • Members page size: 50
   • Posts page size: 20
`

export function FetchesView() {
  const [fetches, setFetches] = useState<FetchEntry[]>([])
  const [total, setTotal] = useState(0)
  const [entityTypes, setEntityTypes] = useState<string[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [entityTypeFilter, setEntityTypeFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [limit, setLimit] = useState(50)

  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const [showQueueLogic, setShowQueueLogic] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    const params = new URLSearchParams()
    if (entityTypeFilter) params.append('entityType', entityTypeFilter)
    if (sourceFilter) params.append('source', sourceFilter)
    params.append('limit', String(limit))

    try {
      const res = await fetch(`${API_BASE}/fetches?${params}`)
      if (!res.ok) throw new Error('Failed to fetch data')
      const data: FetchesResponse = await res.json()
      setFetches(data.fetches || [])
      setTotal(data.total)
      setEntityTypes(data.entityTypes || [])
      setSources(data.sources || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [entityTypeFilter, sourceFilter, limit])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  const formatJson = (jsonStr: string) => {
    try {
      return JSON.stringify(JSON.parse(jsonStr), null, 2)
    } catch {
      return jsonStr
    }
  }

  return (
    <div className="fetches-view">
      <h2>Fetches</h2>

      <details className="queue-logic-info" open={showQueueLogic} onToggle={(e) => setShowQueueLogic((e.target as HTMLDetailsElement).open)}>
        <summary>How is the fetch queue generated?</summary>
        <pre className="queue-logic-content">{QUEUE_LOGIC_INFO}</pre>
      </details>

      <p>Total: {total}</p>

      <fieldset>
        <legend>Filters</legend>
        <div className="filter-row">
          <label>
            Entity Type:
            <select value={entityTypeFilter} onChange={(e) => setEntityTypeFilter(e.target.value)}>
              <option value="">All</option>
              {entityTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
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

          <button onClick={fetchData} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Entity Type</th>
            <th>Entity ID</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {fetches.length === 0 ? (
            <tr>
              <td colSpan={4}>No fetches found</td>
            </tr>
          ) : (
            fetches.map((fetch, index) => (
              <>
                <tr
                  key={index}
                  className="clickable"
                  onClick={() => setExpandedIndex(expandedIndex === index ? null : index)}
                >
                  <td>{formatDate(fetch.fetchedAt)}</td>
                  <td>{fetch.entityType}</td>
                  <td>{fetch.entityId}</td>
                  <td>{fetch.source}</td>
                </tr>
                {expandedIndex === index && (
                  <tr key={`${index}-details`}>
                    <td colSpan={4}>
                      <pre>{formatJson(fetch.rawJson)}</pre>
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

export default FetchesView

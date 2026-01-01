import { useState, useEffect, useRef } from 'react'
import { Network, DataSet } from 'vis-network/standalone'
import './ConnectionGraph.css'

interface Member {
  id: string
  name: string
  slug?: string
  picture?: string
}

interface Connection {
  from: string
  to: string
  fromName: string
  toName: string
  types: {
    like?: number
    comment?: number
  }
  count: number
}

interface ConnectionData {
  members: Member[]
  connections: Connection[]
}

interface ConnectionGraphProps {
  selectionId?: number
  communityIds?: string[]
}

export function ConnectionGraph({ selectionId, communityIds }: ConnectionGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)

  const [data, setData] = useState<ConnectionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showLikes, setShowLikes] = useState(true)
  const [showComments, setShowComments] = useState(true)
  const [isStatic, setIsStatic] = useState(false)

  useEffect(() => {
    loadData()
  }, [selectionId, communityIds])

  useEffect(() => {
    if (data && containerRef.current) {
      initNetwork()
    }
    return () => {
      if (networkRef.current) {
        networkRef.current.destroy()
        networkRef.current = null
      }
    }
  }, [data, showLikes, showComments])

  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()

      if (communityIds && communityIds.length > 0) {
        params.append('communityIds', communityIds.join(','))
      }

      const res = await fetch(`http://localhost:3000/api/connections?${params}`)

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const connectionData = await res.json()
      setData(connectionData)
    } catch (err) {
      console.error('Error loading connection data:', err)
      setError('Fehler beim Laden der Verbindungsdaten')
    } finally {
      setLoading(false)
    }
  }

  const initNetwork = () => {
    if (!containerRef.current || !data) return

    // Filter connections based on settings
    const filteredConnections = data.connections.filter(conn => {
      if (showLikes && conn.types.like) return true
      if (showComments && conn.types.comment) return true
      return false
    })

    // Get involved member IDs
    const involvedIds = new Set<string>()
    filteredConnections.forEach(conn => {
      involvedIds.add(conn.from)
      involvedIds.add(conn.to)
    })

    // Build nodes
    const nodes = new DataSet(
      data.members
        .filter(m => involvedIds.has(m.id))
        .map(m => ({
          id: m.id,
          label: m.name || m.slug || m.id.substring(0, 8),
          title: m.name + (m.slug ? ` (@${m.slug})` : ''),
          shape: m.picture ? 'circularImage' : 'dot',
          image: m.picture || undefined,
          size: 20,
          font: { color: 'var(--text)', size: 11 },
          color: {
            border: '#888',
            background: 'var(--bg)',
            highlight: { border: '#333', background: 'var(--bg-alt)' }
          }
        }))
    )

    // Build edges
    const edges = new DataSet(
      filteredConnections.map((conn, idx) => {
        // Determine color based on type
        let color = '#888'
        const hasLike = conn.types.like && conn.types.like > 0
        const hasComment = conn.types.comment && conn.types.comment > 0

        if (hasLike && hasComment) {
          color = '#666' // Mixed
        } else if (hasLike) {
          color = '#888' // Likes - etwas dunkler
        } else if (hasComment) {
          color = '#555' // Comments - gestrichelt
        }

        const width = Math.min(1 + conn.count * 0.3, 4)

        // Build tooltip
        const tooltipParts = []
        if (conn.types.like) tooltipParts.push(`Likes: ${conn.types.like}x`)
        if (conn.types.comment) tooltipParts.push(`Kommentare: ${conn.types.comment}x`)

        return {
          id: idx,
          from: conn.from,
          to: conn.to,
          color: { color, opacity: 0.6 },
          dashes: Boolean(hasComment && !hasLike), // Gestrichelt nur bei reinen Kommentaren
          width,
          arrows: '',
          title: `${conn.fromName} → ${conn.toName}\n${tooltipParts.join('\n')}\nGesamt: ${conn.count}`
        }
      })
    )

    const options = {
      physics: {
        enabled: !isStatic,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 100,
          springConstant: 0.08,
          damping: 0.8,
          avoidOverlap: 0.5
        },
        stabilization: {
          enabled: true,
          iterations: 200,
          updateInterval: 25
        },
        minVelocity: 0.5,
        maxVelocity: 30
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        hideEdgesOnDrag: true,
        hideEdgesOnZoom: true
      },
      nodes: {
        borderWidth: 2,
        borderWidthSelected: 3
      },
      edges: {
        smooth: {
          enabled: true,
          type: 'continuous',
          roundness: 0.5
        }
      }
    }

    // Destroy old network if exists
    if (networkRef.current) {
      networkRef.current.destroy()
    }

    networkRef.current = new Network(containerRef.current, { nodes, edges }, options)

    // Stop physics after stabilization
    networkRef.current.on('stabilizationIterationsDone', () => {
      if (networkRef.current) {
        networkRef.current.setOptions({ physics: { enabled: false } })
        setIsStatic(true)
      }
    })
  }

  const handleFit = () => {
    if (networkRef.current) {
      networkRef.current.fit({
        animation: {
          duration: 500,
          easingFunction: 'easeInOutQuad'
        }
      })
    }
  }

  const handleTogglePhysics = () => {
    const newStatic = !isStatic
    setIsStatic(newStatic)
    if (networkRef.current) {
      networkRef.current.setOptions({ physics: { enabled: !newStatic } })
    }
  }

  // Calculate stats
  const getStats = () => {
    if (!data) return { members: 0, connections: 0, likes: 0, comments: 0 }

    const filteredConnections = data.connections.filter(conn => {
      if (showLikes && conn.types.like) return true
      if (showComments && conn.types.comment) return true
      return false
    })

    const involvedIds = new Set<string>()
    filteredConnections.forEach(conn => {
      involvedIds.add(conn.from)
      involvedIds.add(conn.to)
    })

    return {
      members: involvedIds.size,
      connections: filteredConnections.length,
      likes: filteredConnections.reduce((sum, c) => sum + (c.types.like || 0), 0),
      comments: filteredConnections.reduce((sum, c) => sum + (c.types.comment || 0), 0)
    }
  }

  if (loading) {
    return (
      <div className="connection-graph">
        <div className="loading-state">Lade Verbindungsdaten...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="connection-graph">
        <div className="error-state">{error}</div>
      </div>
    )
  }

  if (!data || data.connections.length === 0) {
    return (
      <div className="connection-graph">
        <div className="empty-state">
          Keine Verbindungsdaten vorhanden.
          <br />
          <small>Stelle sicher, dass Likes- und Comment-Fetches durchgefuehrt wurden.</small>
        </div>
      </div>
    )
  }

  const stats = getStats()

  return (
    <div className="connection-graph">
      {/* Header mit Filtern */}
      <div className="graph-header">
        <span className="graph-title">Verbindungen</span>
        <div className="graph-filters">
          <label className="filter-checkbox">
            <input
              type="checkbox"
              checked={showLikes}
              onChange={(e) => setShowLikes(e.target.checked)}
            />
            Likes
          </label>
          <label className="filter-checkbox">
            <input
              type="checkbox"
              checked={showComments}
              onChange={(e) => setShowComments(e.target.checked)}
            />
            Kommentare
          </label>
        </div>
      </div>

      {/* Stats */}
      <div className="graph-stats">
        <div className="stat-item">
          <span className="stat-value">{stats.members}</span>
          <span className="stat-label">Mitglieder</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.connections}</span>
          <span className="stat-label">Verbindungen</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.likes}</span>
          <span className="stat-label">Likes</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.comments}</span>
          <span className="stat-label">Kommentare</span>
        </div>
      </div>

      {/* Graph Container */}
      <div className="graph-container" ref={containerRef} />

      {/* Controls */}
      <div className="graph-controls">
        <button onClick={handleFit} className="control-btn">
          Einpassen
        </button>
        <label className="control-checkbox">
          <input
            type="checkbox"
            checked={isStatic}
            onChange={handleTogglePhysics}
          />
          Statisch
        </label>
      </div>

      {/* Top Connections List */}
      <div className="connections-section">
        <div className="section-label">Top Verbindungen</div>
        <div className="connections-list">
          {data.connections
            .filter(conn => {
              if (showLikes && conn.types.like) return true
              if (showComments && conn.types.comment) return true
              return false
            })
            .slice(0, 10)
            .map((conn, i) => (
              <div key={i} className="connection-item">
                <div className="connection-members">
                  <span className="member-name">{conn.fromName || conn.from.substring(0, 8)}</span>
                  <span className="connection-arrow">→</span>
                  <span className="member-name">{conn.toName || conn.to.substring(0, 8)}</span>
                </div>
                <div className="connection-types">
                  {conn.types.like && (
                    <span className="type-badge type-like">{conn.types.like}L</span>
                  )}
                  {conn.types.comment && (
                    <span className="type-badge type-comment">{conn.types.comment}K</span>
                  )}
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}

export default ConnectionGraph

import { useState, useEffect } from 'react'
import './SelectionCard.css'
import { SelectionEditModal } from './SelectionEditModal'
import { ActivityHeatmap } from './ActivityHeatmap'
import { ConnectionGraph } from './ConnectionGraph'

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
  parentId?: number
  derivedSelections?: Selection[]
}

interface Post {
  id: string
  title: string
  content: string
  authorId: string
  authorName: string
  communityId: string
  likes: number
  comments: number
  createdAt: string
}

interface Member {
  id: string
  name: string
  slug: string
  picture?: string
  communityId: string
  joinedAt?: string
  lastOnline?: string
  postCount: number
  level: number
}

interface Community {
  id: string
  name: string
  slug: string
  description?: string
  memberCount: number
  postCount: number
  picture?: string
}

interface SelectionCardProps {
  selection: Selection
  onAddToReport?: (selectionId: number) => void  // Nimmt jetzt die Selection-ID als Parameter
  onSelectionUpdate?: (updated: Selection) => void
  onSelectionDuplicated?: (duplicate: Selection) => void
  showActions?: boolean
  isAddingToReport?: boolean
  isNested?: boolean // Wenn true, keine abgeleiteten Selektionen anzeigen
}

const OUTPUT_TYPE_LABELS: Record<string, string> = {
  member: 'Mitglieder',
  post: 'Posts',
  community: 'Communities'
}

const VIEW_TYPES = ['list', 'table', 'cards', 'activity', 'graph'] as const

export function SelectionCard({
  selection,
  onAddToReport,
  onSelectionUpdate,
  onSelectionDuplicated,
  showActions = true,
  isAddingToReport = false,
  isNested = false
}: SelectionCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [viewType, setViewType] = useState<typeof VIEW_TYPES[number]>('list')
  const [loading, setLoading] = useState(false)
  const [posts, setPosts] = useState<Post[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [total, setTotal] = useState(0)
  const [executed, setExecuted] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [duplicating, setDuplicating] = useState(false)
  const [editingSelection, setEditingSelection] = useState<Selection | null>(null)

  const filters = (() => {
    try {
      return JSON.parse(selection.filtersJson)
    } catch {
      return {}
    }
  })()

  const filterEntries = Object.entries(filters).filter(([_, v]) => v !== null && v !== undefined && v !== '')

  // Execute selection when expanded (for all types)
  useEffect(() => {
    if (expanded && !executed) {
      executeSelection()
    }
  }, [expanded, executed, selection.id])

  const executeSelection = async () => {
    setLoading(true)
    try {
      const res = await fetch(`http://localhost:3000/api/selection/execute?id=${selection.id}`)
      if (res.ok) {
        const data = await res.json()
        setPosts(data.posts || [])
        setMembers(data.members || [])
        setCommunities(data.communities || [])
        setTotal(data.total || 0)
        setExecuted(true)
      }
    } catch (err) {
      console.error('Error executing selection:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDuplicate = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setDuplicating(true)
    try {
      const res = await fetch(`http://localhost:3000/api/selection/duplicate?id=${selection.id}`, {
        method: 'POST'
      })
      if (res.ok) {
        const duplicate = await res.json()
        if (onSelectionDuplicated) {
          onSelectionDuplicated(duplicate)
        }
        // Nach dem Duplizieren das Edit-Modal mit dem Duplikat oeffnen
        setEditingSelection(duplicate)
        setShowEditModal(true)
      }
    } catch (err) {
      console.error('Error duplicating selection:', err)
    } finally {
      setDuplicating(false)
    }
  }

  const handleAddToReport = () => {
    if (onAddToReport) {
      onAddToReport(selection.id)  // Übergibt die ID der aktuellen Selektion
    }
  }

  // Direktes Bearbeiten (fuer abgeleitete Selektionen)
  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingSelection(selection)
    setShowEditModal(true)
  }

  const handleEditSave = (updated: Selection) => {
    setShowEditModal(false)
    setExecuted(false) // Reset um neue Daten zu laden
    setPosts([])
    if (onSelectionUpdate) {
      onSelectionUpdate(updated)
    }
  }

  const truncateContent = (content: string, maxLength: number = 150) => {
    if (!content) return ''
    if (content.length <= maxLength) return content
    return content.substring(0, maxLength) + '...'
  }

  const renderPostsList = () => (
    <div className="posts-list">
      {posts.map(post => (
        <div key={post.id} className="post-item">
          <div className="post-header">
            <span className="post-title">{post.title || '(Kein Titel)'}</span>
            <span className="post-meta">
              {post.likes} Likes · {post.comments} Kommentare
            </span>
          </div>
          <div className="post-content">{truncateContent(post.content)}</div>
          <div className="post-footer">
            <span className="post-author">von {post.authorName || 'Unbekannt'}</span>
            {post.createdAt && <span className="post-date">{new Date(post.createdAt).toLocaleDateString('de-DE')}</span>}
          </div>
        </div>
      ))}
    </div>
  )

  const renderPostsTable = () => (
    <div className="posts-table-container">
      <table className="posts-table">
        <thead>
          <tr>
            <th>Titel</th>
            <th>Autor</th>
            <th>Likes</th>
            <th>Kommentare</th>
            <th>Datum</th>
          </tr>
        </thead>
        <tbody>
          {posts.map(post => (
            <tr key={post.id}>
              <td>{post.title || '(Kein Titel)'}</td>
              <td>{post.authorName || 'Unbekannt'}</td>
              <td>{post.likes}</td>
              <td>{post.comments}</td>
              <td>{post.createdAt ? new Date(post.createdAt).toLocaleDateString('de-DE') : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const renderPostsCards = () => (
    <div className="posts-cards">
      {posts.map(post => (
        <div key={post.id} className="post-card">
          <h4 className="post-card-title">{post.title || '(Kein Titel)'}</h4>
          <p className="post-card-content">{truncateContent(post.content, 100)}</p>
          <div className="post-card-stats">
            <span>{post.likes} Likes</span>
            <span>{post.comments} Kommentare</span>
          </div>
          <div className="post-card-meta">
            <span>{post.authorName || 'Unbekannt'}</span>
          </div>
        </div>
      ))}
    </div>
  )

  const renderPosts = () => {
    if (loading) {
      return <div className="loading-indicator">Lade Posts...</div>
    }

    if (posts.length === 0) {
      return <p className="preview-hint">Keine Posts gefunden.</p>
    }

    switch (viewType) {
      case 'table':
        return renderPostsTable()
      case 'cards':
        return renderPostsCards()
      case 'activity':
        return <ActivityHeatmap />
      case 'graph':
        return <ConnectionGraph />
      default:
        return renderPostsList()
    }
  }

  const renderMembersList = () => (
    <div className="members-list">
      {members.map(member => (
        <div key={member.id} className="member-item">
          <div className="member-header">
            {member.picture && (
              <img src={member.picture} alt={member.name} className="member-avatar" />
            )}
            <span className="member-name">{member.name || member.slug}</span>
            <span className="member-level">Level {member.level}</span>
          </div>
          <div className="member-stats">
            <span>{member.postCount} Posts</span>
            {member.joinedAt && <span>Beigetreten: {member.joinedAt}</span>}
          </div>
        </div>
      ))}
    </div>
  )

  const renderMembersTable = () => (
    <div className="members-table-container">
      <table className="members-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Level</th>
            <th>Posts</th>
            <th>Beigetreten</th>
            <th>Zuletzt online</th>
          </tr>
        </thead>
        <tbody>
          {members.map(member => (
            <tr key={member.id}>
              <td>{member.name || member.slug}</td>
              <td>{member.level}</td>
              <td>{member.postCount}</td>
              <td>{member.joinedAt || '-'}</td>
              <td>{member.lastOnline ? new Date(member.lastOnline).toLocaleDateString('de-DE') : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const renderMembers = () => {
    if (loading) {
      return <div className="loading-indicator">Lade Mitglieder...</div>
    }

    if (members.length === 0) {
      return <p className="preview-hint">Keine Mitglieder gefunden.</p>
    }

    switch (viewType) {
      case 'table':
        return renderMembersTable()
      case 'activity':
        return <ActivityHeatmap />
      case 'graph':
        return <ConnectionGraph />
      default:
        return renderMembersList()
    }
  }

  const renderCommunitiesList = () => (
    <div className="communities-list">
      {communities.map(community => (
        <div key={community.id} className="community-item">
          <div className="community-header">
            {community.picture && (
              <img src={community.picture} alt={community.name} className="community-avatar" />
            )}
            <span className="community-name">{community.name || community.slug}</span>
          </div>
          <div className="community-stats">
            <span>{community.memberCount} Mitglieder</span>
            <span>{community.postCount} Posts</span>
          </div>
          {community.description && (
            <div className="community-description">{truncateContent(community.description, 150)}</div>
          )}
        </div>
      ))}
    </div>
  )

  const renderCommunities = () => {
    if (loading) {
      return <div className="loading-indicator">Lade Communities...</div>
    }

    if (communities.length === 0) {
      return <p className="preview-hint">Keine Communities gefunden.</p>
    }

    return renderCommunitiesList()
  }

  return (
    <>
      <div className="selection-card">
        <div className="selection-header" onClick={() => setExpanded(!expanded)}>
          <div className="selection-info">
            <span className="selection-type">{OUTPUT_TYPE_LABELS[selection.outputType] || selection.outputType}</span>
            <span className="selection-name">{selection.name}</span>
          </div>
          <div className="selection-meta">
            <span className="result-count">{executed ? total : selection.resultCount} Ergebnisse</span>
            {/* Quick-Action Button im Header */}
            {showActions && (
              isNested ? (
                <button
                  onClick={handleEdit}
                  className="header-action-btn"
                  title="Bearbeiten"
                >
                  Bearbeiten
                </button>
              ) : (
                <button
                  onClick={handleDuplicate}
                  className="header-action-btn"
                  disabled={duplicating}
                  title="Duplizieren"
                >
                  {duplicating ? '...' : 'Duplizieren'}
                </button>
              )
            )}
            <span className="expand-icon">{expanded ? '\u25BC' : '\u25B6'}</span>
          </div>
        </div>

        {expanded && (
          <div className="selection-details">
            {/* Filter summary */}
            {filterEntries.length > 0 && (
              <div className="filter-section">
                <strong>Filter:</strong>
                <ul className="filter-list">
                  {filterEntries.map(([key, value]) => (
                    <li key={key}>
                      <span className="filter-key">{key}:</span>
                      <span className="filter-value">{Array.isArray(value) ? value.join(', ') : String(value)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* View type selector */}
            {(selection.outputType === 'post' || selection.outputType === 'member') && (
              <div className="view-selector">
                <span>Ansicht:</span>
                {VIEW_TYPES.map(vt => {
                  // Fuer Posts: list, table, cards
                  // Fuer Members: list, table, activity, graph
                  const postViews = ['list', 'table', 'cards']
                  const memberViews = ['list', 'table', 'activity', 'graph']
                  const relevantViews = selection.outputType === 'member' ? memberViews : postViews

                  if (!relevantViews.includes(vt)) return null

                  return (
                    <button
                      key={vt}
                      className={viewType === vt ? 'active' : ''}
                      onClick={() => setViewType(vt)}
                    >
                      {vt === 'list' ? 'Liste' : vt === 'table' ? 'Tabelle' : vt === 'cards' ? 'Karten' : vt === 'activity' ? 'Aktivitaet' : 'Graph'}
                    </button>
                  )
                })}
              </div>
            )}

            {/* Results */}
            <div className="results-preview">
              {selection.outputType === 'post' ? (
                renderPosts()
              ) : selection.outputType === 'member' ? (
                renderMembers()
              ) : selection.outputType === 'community' ? (
                renderCommunities()
              ) : (
                <p className="preview-hint">Unbekannter Typ: {selection.outputType}</p>
              )}
            </div>

            {/* Actions */}
            {showActions && (
              <div className="selection-actions">
                {!executed && (
                  <button onClick={executeSelection} className="execute-btn" disabled={loading}>
                    {loading ? 'Lade...' : 'Neu laden'}
                  </button>
                )}
                <button
                  onClick={handleAddToReport}
                  className="add-to-report-btn"
                  disabled={isAddingToReport}
                >
                  {isAddingToReport ? 'Wird hinzugefuegt...' : 'In Report uebernehmen'}
                </button>
              </div>
            )}

          </div>
        )}
      </div>

      {/* Abgeleitete Selektionen - IMMER sichtbar (ausserhalb expanded) */}
      {!isNested && selection.derivedSelections && selection.derivedSelections.length > 0 && (
        <div className="derived-selections">
          <div className="derived-list">
            {selection.derivedSelections.map(derived => (
              <SelectionCard
                key={derived.id}
                selection={derived}
                onAddToReport={onAddToReport}
                onSelectionUpdate={onSelectionUpdate}
                onSelectionDuplicated={onSelectionDuplicated}
                showActions={showActions}
                isNested={true}
              />
            ))}
          </div>
        </div>
      )}

      {showEditModal && editingSelection && (
        <SelectionEditModal
          selection={editingSelection}
          onClose={() => {
            setShowEditModal(false)
            setEditingSelection(null)
          }}
          onSave={handleEditSave}
        />
      )}
    </>
  )
}

export default SelectionCard

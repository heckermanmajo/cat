import { useState } from 'react'
import './SelectionCard.css'

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
}

interface SelectionCardProps {
  selection: Selection
  onAddToReport?: (selectionId: number) => void
  showActions?: boolean
}

const OUTPUT_TYPE_LABELS: Record<string, string> = {
  member: 'Mitglieder',
  post: 'Posts',
  community: 'Communities'
}

const VIEW_TYPES = ['list', 'table', 'cards'] as const

export function SelectionCard({ selection, onAddToReport, showActions = true }: SelectionCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [viewType, setViewType] = useState<typeof VIEW_TYPES[number]>('list')

  const filters = (() => {
    try {
      return JSON.parse(selection.filtersJson)
    } catch {
      return {}
    }
  })()

  const filterEntries = Object.entries(filters).filter(([_, v]) => v !== null && v !== undefined && v !== '')

  const handleAddToReport = async () => {
    if (onAddToReport) {
      onAddToReport(selection.id)
    } else {
      // If no callback provided, we could show a dialog to select a report
      alert('Diese Selektion kann in einen Report uebernommen werden.')
    }
  }

  return (
    <div className="selection-card">
      <div className="selection-header" onClick={() => setExpanded(!expanded)}>
        <div className="selection-info">
          <span className="selection-type">{OUTPUT_TYPE_LABELS[selection.outputType] || selection.outputType}</span>
          <span className="selection-name">{selection.name}</span>
        </div>
        <div className="selection-meta">
          <span className="result-count">{selection.resultCount} Ergebnisse</span>
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
                    <span className="filter-value">{String(value)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* View type selector */}
          <div className="view-selector">
            <span>Ansicht:</span>
            {VIEW_TYPES.map(vt => (
              <button
                key={vt}
                className={viewType === vt ? 'active' : ''}
                onClick={() => setViewType(vt)}
              >
                {vt === 'list' ? 'Liste' : vt === 'table' ? 'Tabelle' : 'Karten'}
              </button>
            ))}
          </div>

          {/* Placeholder for results preview */}
          <div className="results-preview">
            <p className="preview-hint">
              Ergebnisse werden hier angezeigt, sobald die Selektion ausgefuehrt wird.
            </p>
          </div>

          {/* Actions */}
          {showActions && (
            <div className="selection-actions">
              <button onClick={handleAddToReport} className="add-to-report-btn">
                In Report uebernehmen
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default SelectionCard

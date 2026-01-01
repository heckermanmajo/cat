import { useState, useEffect } from 'react'
import './SelectionEditModal.css'

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
}

interface SelectionEditModalProps {
  selection: Selection
  onClose: () => void
  onSave: (updated: Selection) => void
}

interface FilterField {
  key: string
  label: string
  type: 'text' | 'number' | 'date' | 'boolean' | 'select'
  description: string
  category: string
  placeholder?: string
  options?: { value: string; label: string }[]
}

const OUTPUT_TYPES = [
  { value: 'post', label: 'Posts', description: 'Filtere und analysiere Posts aus deinen Communities' },
  { value: 'member', label: 'Mitglieder', description: 'Filtere und analysiere Mitglieder aus deinen Communities' },
  { value: 'community', label: 'Communities', description: 'Filtere und vergleiche verschiedene Communities' }
]

// ============== POST FILTER FIELDS ==============
const POST_FILTER_FIELDS: FilterField[] = [
  // Grundlegende Filter
  {
    key: 'community_ids',
    label: 'Community IDs',
    type: 'text',
    category: 'Grundlegend',
    description: 'Kommaseparierte Liste der Community-IDs. Lässt du das leer, werden alle deine Communities durchsucht.',
    placeholder: 'z.B. community-1, community-2'
  },
  {
    key: 'limit',
    label: 'Ergebnis-Limit',
    type: 'number',
    category: 'Grundlegend',
    description: 'Maximale Anzahl der zurückgegebenen Posts. Nützlich für Performance bei großen Datenmengen.',
    placeholder: '100'
  },

  // Engagement Filter
  {
    key: 'likes_min',
    label: 'Mindest-Likes',
    type: 'number',
    category: 'Engagement',
    description: 'Nur Posts mit mindestens dieser Anzahl an Likes. Gut um beliebte Inhalte zu finden.',
    placeholder: '10'
  },
  {
    key: 'likes_max',
    label: 'Max-Likes',
    type: 'number',
    category: 'Engagement',
    description: 'Nur Posts mit höchstens dieser Anzahl an Likes. Hilfreich um "normale" Posts ohne Viral-Effekt zu finden.',
    placeholder: '100'
  },
  {
    key: 'comments_min',
    label: 'Mindest-Kommentare',
    type: 'number',
    category: 'Engagement',
    description: 'Nur Posts mit mindestens dieser Anzahl an Kommentaren. Findet diskussionswürdige Themen.',
    placeholder: '5'
  },
  {
    key: 'comments_max',
    label: 'Max-Kommentare',
    type: 'number',
    category: 'Engagement',
    description: 'Nur Posts mit höchstens dieser Anzahl an Kommentaren.',
    placeholder: '50'
  },

  // Zeitliche Filter
  {
    key: 'created_after',
    label: 'Erstellt nach',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Posts die nach diesem Datum erstellt wurden. Für aktuelle Analysen.',
    placeholder: ''
  },
  {
    key: 'created_before',
    label: 'Erstellt vor',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Posts die vor diesem Datum erstellt wurden. Für historische Analysen.',
    placeholder: ''
  },

  // Autor Filter
  {
    key: 'author_id',
    label: 'Autor ID',
    type: 'text',
    category: 'Autor',
    description: 'Filtere nach einem bestimmten Autor. Die ID findest du im Profil-Link.',
    placeholder: 'user-id-12345'
  },
  {
    key: 'author_name_contains',
    label: 'Autorname enthält',
    type: 'text',
    category: 'Autor',
    description: 'Suche Posts von Autoren deren Name diesen Text enthält (Groß-/Kleinschreibung egal).',
    placeholder: 'Max'
  },
  {
    key: 'exclude_author_ids',
    label: 'Autoren ausschließen',
    type: 'text',
    category: 'Autor',
    description: 'Kommaseparierte Liste von Autor-IDs die ausgeschlossen werden sollen. Z.B. um Admins rauszufiltern.',
    placeholder: 'admin-id-1, admin-id-2'
  },

  // Inhalt Filter
  {
    key: 'title_contains',
    label: 'Titel enthält',
    type: 'text',
    category: 'Inhalt',
    description: 'Suche Posts deren Titel diesen Text enthält (Groß-/Kleinschreibung egal).',
    placeholder: 'Einführung'
  },
  {
    key: 'content_contains',
    label: 'Inhalt enthält',
    type: 'text',
    category: 'Inhalt',
    description: 'Suche Posts deren Text diesen Inhalt enthält. Für Keyword-basierte Analysen.',
    placeholder: 'Strategie'
  },
  {
    key: 'has_title',
    label: 'Hat Titel',
    type: 'boolean',
    category: 'Inhalt',
    description: 'Nur Posts mit (true) oder ohne (false) Titel. Posts ohne Titel sind oft kurze Updates.'
  },
  {
    key: 'has_media',
    label: 'Hat Medien',
    type: 'boolean',
    category: 'Inhalt',
    description: 'Nur Posts mit (true) oder ohne (false) Bilder/Videos. Media-Posts performen oft besser.'
  },
  {
    key: 'content_length_min',
    label: 'Mindest-Textlänge',
    type: 'number',
    category: 'Inhalt',
    description: 'Mindestanzahl Zeichen im Post-Text. Findet ausführliche, hochwertige Posts.',
    placeholder: '500'
  },
  {
    key: 'content_length_max',
    label: 'Max-Textlänge',
    type: 'number',
    category: 'Inhalt',
    description: 'Maximalanzahl Zeichen im Post-Text. Findet kurze, prägnante Posts.',
    placeholder: '200'
  },

  // Sortierung
  {
    key: 'sort_by',
    label: 'Sortieren nach',
    type: 'select',
    category: 'Sortierung',
    description: 'Wie sollen die Ergebnisse sortiert werden?',
    options: [
      { value: 'created_at_desc', label: 'Neueste zuerst' },
      { value: 'created_at_asc', label: 'Älteste zuerst' },
      { value: 'likes_desc', label: 'Meiste Likes zuerst' },
      { value: 'likes_asc', label: 'Wenigste Likes zuerst' },
      { value: 'comments_desc', label: 'Meiste Kommentare zuerst' },
      { value: 'comments_asc', label: 'Wenigste Kommentare zuerst' }
    ]
  }
]

// ============== MEMBER FILTER FIELDS ==============
const MEMBER_FILTER_FIELDS: FilterField[] = [
  // Grundlegende Filter
  {
    key: 'community_ids',
    label: 'Community IDs',
    type: 'text',
    category: 'Grundlegend',
    description: 'Kommaseparierte Liste der Community-IDs. Lässt du das leer, werden alle deine Communities durchsucht.',
    placeholder: 'z.B. community-1, community-2'
  },
  {
    key: 'limit',
    label: 'Ergebnis-Limit',
    type: 'number',
    category: 'Grundlegend',
    description: 'Maximale Anzahl der zurückgegebenen Mitglieder.',
    placeholder: '100'
  },

  // Aktivität Filter
  {
    key: 'post_count_min',
    label: 'Mindest-Posts',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder mit mindestens dieser Anzahl an Posts. Findet aktive Mitglieder.',
    placeholder: '5'
  },
  {
    key: 'post_count_max',
    label: 'Max-Posts',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder mit höchstens dieser Anzahl an Posts. Findet passive oder neue Mitglieder.',
    placeholder: '10'
  },
  {
    key: 'comment_count_min',
    label: 'Mindest-Kommentare',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder mit mindestens dieser Anzahl an Kommentaren. Aktive Community-Teilnehmer.',
    placeholder: '10'
  },
  {
    key: 'comment_count_max',
    label: 'Max-Kommentare',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder mit höchstens dieser Anzahl an Kommentaren.',
    placeholder: '50'
  },
  {
    key: 'likes_given_min',
    label: 'Mindest-Likes vergeben',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder die mindestens so viele Likes vergeben haben. Zeigt Engagement-Level.',
    placeholder: '20'
  },
  {
    key: 'likes_received_min',
    label: 'Mindest-Likes erhalten',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Mitglieder die mindestens so viele Likes erhalten haben. Zeigt Beliebtheit.',
    placeholder: '50'
  },

  // Level & Status
  {
    key: 'level_min',
    label: 'Mindest-Level',
    type: 'number',
    category: 'Level & Status',
    description: 'Nur Mitglieder mit mindestens diesem Level. Findet erfahrene Mitglieder.',
    placeholder: '3'
  },
  {
    key: 'level_max',
    label: 'Max-Level',
    type: 'number',
    category: 'Level & Status',
    description: 'Nur Mitglieder mit höchstens diesem Level. Findet neuere Mitglieder.',
    placeholder: '2'
  },
  {
    key: 'is_admin',
    label: 'Ist Admin',
    type: 'boolean',
    category: 'Level & Status',
    description: 'Nur Admins (true) oder nur normale Mitglieder (false) anzeigen.'
  },
  {
    key: 'has_picture',
    label: 'Hat Profilbild',
    type: 'boolean',
    category: 'Level & Status',
    description: 'Nur Mitglieder mit (true) oder ohne (false) Profilbild. Profilbild zeigt oft ernsthaftes Interesse.'
  },

  // Zeitliche Filter
  {
    key: 'joined_after',
    label: 'Beigetreten nach',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Mitglieder die nach diesem Datum beigetreten sind. Findet neue Mitglieder.',
    placeholder: ''
  },
  {
    key: 'joined_before',
    label: 'Beigetreten vor',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Mitglieder die vor diesem Datum beigetreten sind. Findet langjährige Mitglieder.',
    placeholder: ''
  },
  {
    key: 'last_online_after',
    label: 'Zuletzt online nach',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Mitglieder die nach diesem Datum zuletzt online waren. Findet aktive Nutzer.',
    placeholder: ''
  },
  {
    key: 'last_online_before',
    label: 'Zuletzt online vor',
    type: 'date',
    category: 'Zeitraum',
    description: 'Nur Mitglieder die vor diesem Datum zuletzt online waren. Findet inaktive Nutzer für Reaktivierung.',
    placeholder: ''
  },

  // Name Filter
  {
    key: 'name_contains',
    label: 'Name enthält',
    type: 'text',
    category: 'Name & Suche',
    description: 'Suche Mitglieder deren Name diesen Text enthält (Groß-/Kleinschreibung egal).',
    placeholder: 'Max'
  },
  {
    key: 'bio_contains',
    label: 'Bio enthält',
    type: 'text',
    category: 'Name & Suche',
    description: 'Suche Mitglieder deren Bio/Beschreibung diesen Text enthält. Gut für Zielgruppenanalyse.',
    placeholder: 'Coach'
  },
  {
    key: 'exclude_member_ids',
    label: 'Mitglieder ausschließen',
    type: 'text',
    category: 'Name & Suche',
    description: 'Kommaseparierte Liste von Mitglieder-IDs die ausgeschlossen werden sollen.',
    placeholder: 'member-id-1, member-id-2'
  },

  // Sortierung
  {
    key: 'sort_by',
    label: 'Sortieren nach',
    type: 'select',
    category: 'Sortierung',
    description: 'Wie sollen die Ergebnisse sortiert werden?',
    options: [
      { value: 'joined_at_desc', label: 'Neueste zuerst' },
      { value: 'joined_at_asc', label: 'Älteste zuerst' },
      { value: 'level_desc', label: 'Höchstes Level zuerst' },
      { value: 'level_asc', label: 'Niedrigstes Level zuerst' },
      { value: 'post_count_desc', label: 'Meiste Posts zuerst' },
      { value: 'last_online_desc', label: 'Zuletzt aktiv zuerst' },
      { value: 'name_asc', label: 'Name A-Z' }
    ]
  }
]

// ============== COMMUNITY FILTER FIELDS ==============
const COMMUNITY_FILTER_FIELDS: FilterField[] = [
  // Grundlegende Filter
  {
    key: 'community_ids',
    label: 'Community IDs',
    type: 'text',
    category: 'Grundlegend',
    description: 'Kommaseparierte Liste der Community-IDs die du vergleichen/analysieren möchtest.',
    placeholder: 'z.B. community-1, community-2'
  },
  {
    key: 'limit',
    label: 'Ergebnis-Limit',
    type: 'number',
    category: 'Grundlegend',
    description: 'Maximale Anzahl der zurückgegebenen Communities.',
    placeholder: '50'
  },

  // Größe Filter
  {
    key: 'member_count_min',
    label: 'Mindest-Mitglieder',
    type: 'number',
    category: 'Größe',
    description: 'Nur Communities mit mindestens dieser Anzahl an Mitgliedern. Für etablierte Communities.',
    placeholder: '100'
  },
  {
    key: 'member_count_max',
    label: 'Max-Mitglieder',
    type: 'number',
    category: 'Größe',
    description: 'Nur Communities mit höchstens dieser Anzahl an Mitgliedern. Für kleinere, intimere Gruppen.',
    placeholder: '1000'
  },
  {
    key: 'post_count_min',
    label: 'Mindest-Posts',
    type: 'number',
    category: 'Größe',
    description: 'Nur Communities mit mindestens dieser Anzahl an Posts. Zeigt Aktivitätslevel.',
    placeholder: '50'
  },
  {
    key: 'post_count_max',
    label: 'Max-Posts',
    type: 'number',
    category: 'Größe',
    description: 'Nur Communities mit höchstens dieser Anzahl an Posts.',
    placeholder: '500'
  },

  // Inhalt Filter
  {
    key: 'name_contains',
    label: 'Name enthält',
    type: 'text',
    category: 'Inhalt',
    description: 'Suche Communities deren Name diesen Text enthält.',
    placeholder: 'Fitness'
  },
  {
    key: 'description_contains',
    label: 'Beschreibung enthält',
    type: 'text',
    category: 'Inhalt',
    description: 'Suche Communities deren Beschreibung diesen Text enthält. Für thematische Analysen.',
    placeholder: 'Business'
  },
  {
    key: 'has_picture',
    label: 'Hat Logo/Bild',
    type: 'boolean',
    category: 'Inhalt',
    description: 'Nur Communities mit (true) oder ohne (false) Logo. Zeigt Professionalitätsgrad.'
  },

  // Aktivität
  {
    key: 'avg_posts_per_day_min',
    label: 'Min. Posts/Tag',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Communities mit mindestens dieser durchschnittlichen Posts pro Tag.',
    placeholder: '2'
  },
  {
    key: 'active_members_percentage_min',
    label: 'Min. aktive Mitglieder %',
    type: 'number',
    category: 'Aktivität',
    description: 'Nur Communities mit mindestens diesem Prozentsatz aktiver Mitglieder (letzte 30 Tage).',
    placeholder: '20'
  },

  // Sortierung
  {
    key: 'sort_by',
    label: 'Sortieren nach',
    type: 'select',
    category: 'Sortierung',
    description: 'Wie sollen die Ergebnisse sortiert werden?',
    options: [
      { value: 'member_count_desc', label: 'Größte zuerst' },
      { value: 'member_count_asc', label: 'Kleinste zuerst' },
      { value: 'post_count_desc', label: 'Aktivste zuerst' },
      { value: 'name_asc', label: 'Name A-Z' },
      { value: 'created_at_desc', label: 'Neueste zuerst' }
    ]
  }
]

export function SelectionEditModal({ selection, onClose, onSave }: SelectionEditModalProps) {
  const [name, setName] = useState(selection.name)
  const [outputType, setOutputType] = useState(selection.outputType)
  const [filters, setFilters] = useState<Record<string, any>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set())

  useEffect(() => {
    try {
      const parsed = JSON.parse(selection.filtersJson)
      setFilters(parsed || {})
    } catch {
      setFilters({})
    }
  }, [selection.filtersJson])

  const getFilterFields = (): FilterField[] => {
    switch (outputType) {
      case 'post':
        return POST_FILTER_FIELDS
      case 'member':
        return MEMBER_FILTER_FIELDS
      case 'community':
        return COMMUNITY_FILTER_FIELDS
      default:
        return []
    }
  }

  // Gruppiere Felder nach Kategorie
  const getFieldsByCategory = () => {
    const fields = getFilterFields()
    const categories: Record<string, FilterField[]> = {}
    fields.forEach(field => {
      if (!categories[field.category]) {
        categories[field.category] = []
      }
      categories[field.category].push(field)
    })
    return categories
  }

  const toggleCategory = (category: string) => {
    setCollapsedCategories(prev => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  const handleFilterChange = (key: string, value: string | boolean, type: string) => {
    setFilters(prev => {
      const newFilters = { ...prev }
      if (value === '' || value === null || value === undefined) {
        delete newFilters[key]
      } else if (type === 'number') {
        const num = parseInt(value as string)
        if (isNaN(num)) {
          delete newFilters[key]
        } else {
          newFilters[key] = num
        }
      } else if (type === 'boolean') {
        newFilters[key] = value === 'true' || value === true
      } else if (key.includes('_ids') && typeof value === 'string') {
        newFilters[key] = value.split(',').map(s => s.trim()).filter(Boolean)
      } else {
        newFilters[key] = value
      }
      return newFilters
    })
  }

  const getFilterValue = (key: string, type: string): string => {
    const val = filters[key]
    if (val === undefined || val === null) return ''
    if (type === 'boolean') {
      if (val === true) return 'true'
      if (val === false) return 'false'
      return ''
    }
    if (Array.isArray(val)) return val.join(', ')
    return String(val)
  }

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name ist erforderlich')
      return
    }

    setSaving(true)
    setError('')

    try {
      const res = await fetch(`http://localhost:3000/api/selection?id=${selection.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          outputType,
          filters
        })
      })

      if (!res.ok) {
        throw new Error('Speichern fehlgeschlagen')
      }

      const updated = await res.json()
      onSave(updated)
    } catch (err) {
      setError('Fehler beim Speichern')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  // Zähle aktive Filter pro Kategorie
  const getActiveFilterCount = (fields: FilterField[]) => {
    return fields.filter(f => {
      const val = filters[f.key]
      return val !== undefined && val !== null && val !== ''
    }).length
  }

  const renderField = (field: FilterField) => {
    const value = getFilterValue(field.key, field.type)
    const hasValue = value !== ''

    return (
      <div className={`filter-field ${hasValue ? 'has-value' : ''}`} key={field.key}>
        <div className="field-header">
          <label htmlFor={`filter-${field.key}`}>{field.label}</label>
          {hasValue && (
            <button
              className="clear-field"
              onClick={() => handleFilterChange(field.key, '', field.type)}
              title="Zurücksetzen"
            >
              ×
            </button>
          )}
        </div>

        {field.type === 'boolean' ? (
          <select
            id={`filter-${field.key}`}
            value={value}
            onChange={e => handleFilterChange(field.key, e.target.value, field.type)}
            className="field-input"
          >
            <option value="">— Nicht gesetzt —</option>
            <option value="true">Ja</option>
            <option value="false">Nein</option>
          </select>
        ) : field.type === 'select' ? (
          <select
            id={`filter-${field.key}`}
            value={value}
            onChange={e => handleFilterChange(field.key, e.target.value, field.type)}
            className="field-input"
          >
            <option value="">— Nicht gesetzt —</option>
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        ) : field.type === 'date' ? (
          <input
            id={`filter-${field.key}`}
            type="date"
            value={value}
            onChange={e => handleFilterChange(field.key, e.target.value, field.type)}
            className="field-input"
          />
        ) : (
          <input
            id={`filter-${field.key}`}
            type={field.type}
            value={value}
            onChange={e => handleFilterChange(field.key, e.target.value, field.type)}
            placeholder={field.placeholder || ''}
            className="field-input"
          />
        )}

        <p className="field-description">{field.description}</p>
      </div>
    )
  }

  const categories = getFieldsByCategory()
  const selectedTypeInfo = OUTPUT_TYPES.find(t => t.value === outputType)

  return (
    <div className="modal-backdrop fullscreen" onClick={handleBackdropClick}>
      <div className="modal-content fullscreen">
        <div className="modal-header">
          <div className="header-left">
            <h2>Selection bearbeiten</h2>
            <span className="selection-id">ID: {selection.id}</span>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          {error && <div className="modal-error">{error}</div>}

          <div className="modal-layout">
            {/* Linke Spalte: Grundeinstellungen */}
            <div className="modal-sidebar">
              <div className="sidebar-section">
                <h3>Grundeinstellungen</h3>

                <div className="form-group">
                  <label htmlFor="sel-name">Name der Selektion</label>
                  <input
                    id="sel-name"
                    type="text"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="z.B. Aktive Mitglieder Q4"
                    className="field-input"
                  />
                  <p className="field-description">
                    Ein aussagekräftiger Name hilft dir, Selektionen später wiederzufinden.
                  </p>
                </div>

                <div className="form-group">
                  <label htmlFor="sel-type">Ergebnis-Typ</label>
                  <select
                    id="sel-type"
                    value={outputType}
                    onChange={e => {
                      setOutputType(e.target.value)
                      setFilters({}) // Reset filters when type changes
                    }}
                    className="field-input"
                  >
                    {OUTPUT_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                  {selectedTypeInfo && (
                    <p className="field-description">{selectedTypeInfo.description}</p>
                  )}
                </div>
              </div>

              <div className="sidebar-section">
                <h3>Aktive Filter</h3>
                <pre className="filter-preview">
                  {Object.keys(filters).length === 0
                    ? '(keine Filter gesetzt)'
                    : JSON.stringify(filters, null, 2)}
                </pre>
              </div>

              <div className="sidebar-section stats">
                <div className="stat-item">
                  <span className="stat-value">{selection.resultCount}</span>
                  <span className="stat-label">Ergebnisse (zuletzt)</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{Object.keys(filters).length}</span>
                  <span className="stat-label">Filter aktiv</span>
                </div>
              </div>
            </div>

            {/* Rechte Spalte: Filter nach Kategorien */}
            <div className="modal-main">
              <div className="filter-categories">
                {Object.keys(categories).length === 0 ? (
                  <p className="no-filters">Keine Filter für diesen Typ verfügbar.</p>
                ) : (
                  Object.entries(categories).map(([category, fields]) => {
                    const isCollapsed = collapsedCategories.has(category)
                    const activeCount = getActiveFilterCount(fields)

                    return (
                      <div className="filter-category" key={category}>
                        <div
                          className="category-header"
                          onClick={() => toggleCategory(category)}
                        >
                          <span className="category-toggle">{isCollapsed ? '▶' : '▼'}</span>
                          <span className="category-name">{category}</span>
                          <span className="category-count">
                            {fields.length} Filter
                            {activeCount > 0 && (
                              <span className="active-badge">{activeCount} aktiv</span>
                            )}
                          </span>
                        </div>

                        {!isCollapsed && (
                          <div className="category-fields">
                            {fields.map(field => renderField(field))}
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <div className="footer-info">
            Erstellt von: {selection.createdBy || 'System'}
          </div>
          <div className="footer-actions">
            <button className="btn-cancel" onClick={onClose}>Abbrechen</button>
            <button className="btn-save" onClick={handleSave} disabled={saving}>
              {saving ? 'Speichert...' : 'Speichern'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SelectionEditModal

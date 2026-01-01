import { useState, useEffect, useRef } from 'react'
import './PromptTemplatePanel.css'

const API_BASE = '/api'

interface PromptTemplate {
  id: number
  name: string
  content: string
  description: string
  category: string
  createdAt: string
  updatedAt: string
}

interface PromptTemplatePanelProps {
  onInsert: (text: string) => void
}

export function PromptTemplatePanel({ onInsert }: PromptTemplatePanelProps) {
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())

  // Edit/Create modal state
  const [showModal, setShowModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<PromptTemplate | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    content: '',
    description: '',
    category: ''
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Menu state
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadTemplates()
  }, [])

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    if (openMenuId !== null) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [openMenuId])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/prompt-templates`)
      if (res.ok) {
        const data = await res.json()
        setTemplates(data.templates || [])
        setCategories(data.categories || [])
        // Expand all categories by default
        if (data.categories && data.categories.length > 0) {
          setExpandedCategories(new Set(data.categories))
        }
      }
    } catch (err) {
      console.error('Failed to load templates:', err)
    } finally {
      setLoading(false)
    }
  }

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  const groupedTemplates = templates.reduce((acc, t) => {
    const cat = t.category || 'Allgemein'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(t)
    return acc
  }, {} as Record<string, PromptTemplate[]>)

  const openCreateModal = () => {
    setEditingTemplate(null)
    setFormData({ name: '', content: '', description: '', category: '' })
    setError('')
    setShowModal(true)
  }

  const openEditModal = (template: PromptTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      content: template.content,
      description: template.description,
      category: template.category
    })
    setError('')
    setShowModal(true)
    setOpenMenuId(null)
  }

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Name ist erforderlich')
      return
    }
    if (!formData.content.trim()) {
      setError('Prompt-Text ist erforderlich')
      return
    }

    setSaving(true)
    setError('')

    try {
      const url = editingTemplate
        ? `${API_BASE}/prompt-template?id=${editingTemplate.id}`
        : `${API_BASE}/prompt-templates`

      const res = await fetch(url, {
        method: editingTemplate ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name.trim(),
          content: formData.content.trim(),
          description: formData.description.trim(),
          category: formData.category.trim() || 'Allgemein'
        })
      })

      if (res.ok) {
        await loadTemplates()
        setShowModal(false)
      } else {
        setError('Speichern fehlgeschlagen')
      }
    } catch (err) {
      console.error('Save failed:', err)
      setError('Speichern fehlgeschlagen')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Template wirklich loeschen?')) return

    try {
      const res = await fetch(`${API_BASE}/prompt-template?id=${id}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        await loadTemplates()
      }
    } catch (err) {
      console.error('Delete failed:', err)
    }
    setOpenMenuId(null)
  }

  const handleInsertClick = (template: PromptTemplate) => {
    onInsert(template.content)
  }

  return (
    <div className="prompt-template-panel">
      <div className="template-panel-header">
        <span className="panel-title">Templates</span>
        <button className="add-template-btn" onClick={openCreateModal} title="Neues Template">
          +
        </button>
      </div>

      <div className="template-list">
        {loading ? (
          <p className="loading-hint">Lade Templates...</p>
        ) : templates.length === 0 ? (
          <div className="empty-templates">
            <p>Keine Templates vorhanden</p>
            <button onClick={openCreateModal}>Erstes Template erstellen</button>
          </div>
        ) : (
          Object.entries(groupedTemplates).map(([category, categoryTemplates]) => (
            <div key={category} className="template-category">
              <div
                className="category-header"
                onClick={() => toggleCategory(category)}
              >
                <span className="expand-icon">
                  {expandedCategories.has(category) ? '\u25BC' : '\u25B6'}
                </span>
                <span className="category-name">{category}</span>
                <span className="category-count">{categoryTemplates.length}</span>
              </div>

              {expandedCategories.has(category) && (
                <div className="category-templates">
                  {categoryTemplates.map(template => (
                    <div key={template.id} className="template-item">
                      <div
                        className="template-info"
                        onClick={() => handleInsertClick(template)}
                        title={template.description || template.content}
                      >
                        <span className="template-name">{template.name}</span>
                        {template.description && (
                          <span className="template-desc">{template.description}</span>
                        )}
                      </div>
                      <div className="template-menu-container">
                        <button
                          className="template-menu-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            setOpenMenuId(openMenuId === template.id ? null : template.id)
                          }}
                        >
                          ⋮
                        </button>
                        {openMenuId === template.id && (
                          <div className="template-menu-dropdown" ref={menuRef}>
                            <button onClick={() => openEditModal(template)}>
                              Bearbeiten
                            </button>
                            <button
                              className="delete-option"
                              onClick={() => handleDelete(template.id)}
                            >
                              Loeschen
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="template-modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="template-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingTemplate ? 'Template bearbeiten' : 'Neues Template'}</h3>
              <button className="close-btn" onClick={() => setShowModal(false)}>X</button>
            </div>

            <div className="modal-body">
              {error && <div className="error-message">{error}</div>}

              <div className="form-field">
                <label htmlFor="template-name">Name *</label>
                <input
                  id="template-name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="z.B. Mitglieder-Analyse"
                />
              </div>

              <div className="form-field">
                <label htmlFor="template-category">Kategorie</label>
                <input
                  id="template-category"
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                  placeholder="z.B. Analyse (Standard: Allgemein)"
                  list="category-suggestions"
                />
                <datalist id="category-suggestions">
                  {categories.map(cat => (
                    <option key={cat} value={cat} />
                  ))}
                </datalist>
              </div>

              <div className="form-field">
                <label htmlFor="template-description">Beschreibung</label>
                <input
                  id="template-description"
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Kurze Beschreibung (optional)"
                />
              </div>

              <div className="form-field">
                <label htmlFor="template-content">Prompt-Text *</label>
                <textarea
                  id="template-content"
                  value={formData.content}
                  onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                  placeholder="Der Text, der in das Chat-Eingabefeld eingefuegt wird..."
                  rows={6}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button className="cancel-btn" onClick={() => setShowModal(false)}>
                Abbrechen
              </button>
              <button
                className="save-btn"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? 'Speichern...' : 'Speichern'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PromptTemplatePanel

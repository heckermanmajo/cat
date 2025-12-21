import { useState, useEffect } from 'react'
import SelectionCard from './SelectionCard'
import './ReportView.css'

const API_BASE = '/api'

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
}

interface ReportBlock {
  id: number
  reportId: number
  blockType: 'text' | 'selection'
  position: number
  content?: string
  selectionId?: number
  viewType: string
}

interface Report {
  id: number
  name: string
  createdAt: string
  blocks: ReportBlock[]
}

export function ReportView() {
  const [reports, setReports] = useState<Report[]>([])
  const [activeReport, setActiveReport] = useState<Report | null>(null)
  const [selections, setSelections] = useState<Selection[]>([])
  const [loading, setLoading] = useState(false)
  const [newBlockType, setNewBlockType] = useState<'text' | 'selection'>('text')
  const [newBlockContent, setNewBlockContent] = useState('')
  const [selectedSelectionId, setSelectedSelectionId] = useState<number | null>(null)

  useEffect(() => {
    loadReports()
    loadSelections()
  }, [])

  useEffect(() => {
    if (activeReport) {
      loadReportDetails(activeReport.id)
    }
  }, [activeReport?.id])

  const loadReports = async () => {
    try {
      const res = await fetch(`${API_BASE}/reports`)
      if (res.ok) {
        const data = await res.json()
        setReports(data)
      }
    } catch (err) {
      console.error('Failed to load reports:', err)
    }
  }

  const loadSelections = async () => {
    try {
      const res = await fetch(`${API_BASE}/selections`)
      if (res.ok) {
        const data = await res.json()
        setSelections(data)
      }
    } catch (err) {
      console.error('Failed to load selections:', err)
    }
  }

  const loadReportDetails = async (reportId: number) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/report?id=${reportId}`)
      if (res.ok) {
        const data = await res.json()
        setActiveReport(data)
      }
    } catch (err) {
      console.error('Failed to load report details:', err)
    } finally {
      setLoading(false)
    }
  }

  const createNewReport = async () => {
    const name = prompt('Name for the new report:', 'New Report')
    if (!name) return

    try {
      const res = await fetch(`${API_BASE}/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      if (res.ok) {
        const report = await res.json()
        setReports(prev => [report, ...prev])
        setActiveReport(report)
      }
    } catch (err) {
      console.error('Failed to create report:', err)
    }
  }

  const deleteReport = async (reportId: number) => {
    if (!confirm('Really delete report?')) return

    try {
      const res = await fetch(`${API_BASE}/report?id=${reportId}`, { method: 'DELETE' })
      if (res.ok) {
        setReports(prev => prev.filter(r => r.id !== reportId))
        if (activeReport?.id === reportId) {
          setActiveReport(null)
        }
      }
    } catch (err) {
      console.error('Failed to delete report:', err)
    }
  }

  const addBlock = async () => {
    if (!activeReport) return

    const body: Record<string, unknown> = {
      blockType: newBlockType,
      viewType: 'list'
    }

    if (newBlockType === 'text') {
      if (!newBlockContent.trim()) {
        alert('Please enter text')
        return
      }
      body.content = newBlockContent
    } else {
      if (!selectedSelectionId) {
        alert('Please select a selection')
        return
      }
      body.selectionId = selectedSelectionId
    }

    try {
      const res = await fetch(`${API_BASE}/report-blocks?reportId=${activeReport.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      if (res.ok) {
        // Reload report to get updated blocks
        await loadReportDetails(activeReport.id)
        setNewBlockContent('')
        setSelectedSelectionId(null)
      }
    } catch (err) {
      console.error('Failed to add block:', err)
    }
  }

  const deleteBlock = async (blockId: number) => {
    try {
      const res = await fetch(`${API_BASE}/report-block?id=${blockId}`, { method: 'DELETE' })
      if (res.ok && activeReport) {
        await loadReportDetails(activeReport.id)
      }
    } catch (err) {
      console.error('Failed to delete block:', err)
    }
  }

  const getSelectionById = (id: number): Selection | undefined => {
    return selections.find(s => s.id === id)
  }

  return (
    <div className="report-view">
      {/* Sidebar with report list */}
      <aside className="report-sidebar">
        <button className="new-report-btn" onClick={createNewReport}>
          + New Report
        </button>
        <div className="report-list">
          {reports.map(report => (
            <div
              key={report.id}
              className={`report-item ${activeReport?.id === report.id ? 'active' : ''}`}
              onClick={() => setActiveReport(report)}
            >
              <span className="report-name">{report.name}</span>
              <button
                className="delete-btn"
                onClick={(e) => { e.stopPropagation(); deleteReport(report.id) }}
                title="Delete report"
              >
                x
              </button>
            </div>
          ))}
          {reports.length === 0 && (
            <p className="no-reports">No reports available</p>
          )}
        </div>
      </aside>

      {/* Main report area */}
      <main className="report-main">
        {activeReport ? (
          <>
            <div className="report-header">
              <h2>{activeReport.name}</h2>
            </div>

            <div className="report-content">
              {loading ? (
                <p className="loading">Loading report...</p>
              ) : (
                <>
                  {/* Render blocks */}
                  {activeReport.blocks && activeReport.blocks.length > 0 ? (
                    <div className="report-blocks">
                      {activeReport.blocks.map(block => (
                        <div key={block.id} className={`report-block ${block.blockType}`}>
                          <button
                            className="block-delete-btn"
                            onClick={() => deleteBlock(block.id)}
                            title="Remove block"
                          >
                            x
                          </button>
                          {block.blockType === 'text' ? (
                            <div className="text-block">
                              <p>{block.content}</p>
                            </div>
                          ) : (
                            <div className="selection-block">
                              {block.selectionId && getSelectionById(block.selectionId) ? (
                                <SelectionCard
                                  selection={getSelectionById(block.selectionId)!}
                                  showActions={false}
                                />
                              ) : (
                                <p className="missing-selection">Selection not found</p>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-report">
                      <p>This report is still empty.</p>
                      <p className="hint">Add text or selections to create your report.</p>
                    </div>
                  )}

                  {/* Add block form */}
                  <div className="add-block-section">
                    <h4>Add block</h4>
                    <div className="block-type-selector">
                      <button
                        className={newBlockType === 'text' ? 'active' : ''}
                        onClick={() => setNewBlockType('text')}
                      >
                        Text
                      </button>
                      <button
                        className={newBlockType === 'selection' ? 'active' : ''}
                        onClick={() => setNewBlockType('selection')}
                      >
                        Selection
                      </button>
                    </div>

                    {newBlockType === 'text' ? (
                      <textarea
                        value={newBlockContent}
                        onChange={(e) => setNewBlockContent(e.target.value)}
                        placeholder="Enter text..."
                        rows={3}
                      />
                    ) : (
                      <select
                        value={selectedSelectionId || ''}
                        onChange={(e) => setSelectedSelectionId(Number(e.target.value) || null)}
                      >
                        <option value="">-- Select a selection --</option>
                        {selections.map(sel => (
                          <option key={sel.id} value={sel.id}>
                            {sel.name} ({sel.outputType})
                          </option>
                        ))}
                      </select>
                    )}

                    <button className="add-block-btn" onClick={addBlock}>
                      Add
                    </button>
                  </div>
                </>
              )}
            </div>
          </>
        ) : (
          <div className="no-report-selected">
            <p>Select a report from the list or create a new one.</p>
            <button onClick={createNewReport}>Create new report</button>
          </div>
        )}
      </main>
    </div>
  )
}

export default ReportView

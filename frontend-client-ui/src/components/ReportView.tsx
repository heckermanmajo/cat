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

  const getSelectionById = (id: number): Selection | undefined => {
    return selections.find(s => s.id === id)
  }

  return (
    <div className="report-view">
      {/* Sidebar with report list */}
      <aside className="report-sidebar">
        <div className="sidebar-hint">
          Reports werden automatisch in Chats erstellt.
        </div>

        <div className="sidebar-section">
          <h4>Reports</h4>
          <div className="report-list">
            {reports.map(report => (
              <div
                key={report.id}
                className={`report-item ${activeReport?.id === report.id ? 'active' : ''}`}
                onClick={() => setActiveReport(report)}
              >
                <span className="report-name">{report.name}</span>
              </div>
            ))}
            {reports.length === 0 && (
              <p className="no-reports">Keine Reports vorhanden</p>
            )}
          </div>
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
                        <div key={block.id} className="report-block">
                          {/* Text-Inhalt anzeigen wenn vorhanden */}
                          {block.content && (
                            <div className="text-block">
                              <p>{block.content}</p>
                            </div>
                          )}
                          {/* Selection anzeigen wenn vorhanden */}
                          {block.selectionId && (
                            <div className="selection-block">
                              {getSelectionById(block.selectionId) ? (
                                <SelectionCard
                                  selection={getSelectionById(block.selectionId)!}
                                  showActions={false}
                                />
                              ) : (
                                <p className="missing-selection">Selection nicht gefunden (ID: {block.selectionId})</p>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-report">
                      <p>Dieser Report ist noch leer.</p>
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        ) : (
          <div className="no-report-selected">
            <p>Waehle einen Report aus der Liste.</p>
            <p className="hint">Reports werden automatisch in Chats erstellt, wenn du Selektionen hinzufuegst.</p>
          </div>
        )}
      </main>
    </div>
  )
}

export default ReportView

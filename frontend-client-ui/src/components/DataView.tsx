import { useState, useEffect, useCallback } from 'react'
import './DataView.css'

interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
}

interface TableInfo {
  name: string
  type: string
  columns: ColumnInfo[]
  rowCount: number
}

interface SchemaResponse {
  duckdb: TableInfo[]
  sqlite: TableInfo[]
}

interface TableDataResponse {
  columns: string[]
  rows: (string | number | null)[][]
  total: number
}

const API_BASE = '/api'

export function DataView() {
  const [schema, setSchema] = useState<SchemaResponse | null>(null)
  const [selectedTable, setSelectedTable] = useState<{ name: string; db: string } | null>(null)
  const [tableData, setTableData] = useState<TableDataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedRow, setExpandedRow] = useState<number | null>(null)
  const [limit, setLimit] = useState(50)

  const fetchSchema = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/schema`)
      if (!res.ok) throw new Error('Failed to fetch schema')
      const data: SchemaResponse = await res.json()
      setSchema(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchTableData = useCallback(async (tableName: string, db: string) => {
    setLoading(true)
    setError(null)
    setExpandedRow(null)
    try {
      const res = await fetch(`${API_BASE}/table-data?table=${tableName}&db=${db}&limit=${limit}`)
      if (!res.ok) throw new Error('Failed to fetch table data')
      const data: TableDataResponse = await res.json()
      setTableData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetchSchema()
  }, [fetchSchema])

  useEffect(() => {
    if (selectedTable) {
      fetchTableData(selectedTable.name, selectedTable.db)
    }
  }, [selectedTable, fetchTableData])

  const handleTableClick = (tableName: string, db: string) => {
    setSelectedTable({ name: tableName, db })
  }

  const formatCellValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'NULL'
    if (typeof value === 'string') {
      if (value.length > 100) return value.substring(0, 100) + '...'
      return value
    }
    return String(value)
  }

  const isJsonColumn = (columnName: string): boolean => {
    return columnName.includes('json') || columnName === 'raw_json' || columnName === 'data_json'
  }

  const formatJson = (jsonStr: string): string => {
    try {
      return JSON.stringify(JSON.parse(jsonStr), null, 2)
    } catch {
      return jsonStr
    }
  }

  const getSelectedTableInfo = (): TableInfo | undefined => {
    if (!schema || !selectedTable) return undefined
    const tables = selectedTable.db === 'duckdb' ? schema.duckdb : schema.sqlite
    return tables.find(t => t.name === selectedTable.name)
  }

  return (
    <div className="data-view">
      <h2>Data View</h2>
      <p>Inspect all database tables and their schemas</p>

      {error && <p className="error">{error}</p>}

      <div className="data-view-layout">
        {/* Sidebar with table list */}
        <aside className="table-sidebar">
          <h3>DuckDB Tables</h3>
          {schema?.duckdb.map(table => (
            <button
              key={table.name}
              className={`table-btn ${selectedTable?.name === table.name && selectedTable?.db === 'duckdb' ? 'active' : ''}`}
              onClick={() => handleTableClick(table.name, 'duckdb')}
            >
              {table.name}
              {table.rowCount > 0 && <span className="row-count">({table.rowCount})</span>}
            </button>
          ))}

          <h3>SQLite Tables</h3>
          {schema?.sqlite.map(table => (
            <button
              key={table.name}
              className={`table-btn ${selectedTable?.name === table.name && selectedTable?.db === 'sqlite' ? 'active' : ''}`}
              onClick={() => handleTableClick(table.name, 'sqlite')}
            >
              {table.name}
            </button>
          ))}
        </aside>

        {/* Main content area */}
        <main className="table-content">
          {!selectedTable ? (
            <div className="placeholder">
              <p>Select a table from the sidebar to view its schema and data</p>
            </div>
          ) : (
            <>
              {/* Schema section */}
              <section className="schema-section">
                <h3>
                  {selectedTable.name}
                  <span className="db-badge">{selectedTable.db}</span>
                </h3>

                <details open>
                  <summary>Schema ({getSelectedTableInfo()?.columns.length || 0} columns)</summary>
                  <table className="schema-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Type</th>
                        <th>Nullable</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getSelectedTableInfo()?.columns.map(col => (
                        <tr key={col.name}>
                          <td><code>{col.name}</code></td>
                          <td>{col.type}</td>
                          <td>{col.nullable ? 'Yes' : 'No'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              </section>

              {/* Data section */}
              <section className="data-section">
                <div className="data-header">
                  <h4>Data {tableData && `(${tableData.total} total)`}</h4>
                  <div className="data-controls">
                    <label>
                      Limit:
                      <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={500}>500</option>
                      </select>
                    </label>
                    <button onClick={() => fetchTableData(selectedTable.name, selectedTable.db)} disabled={loading}>
                      {loading ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>
                </div>

                {tableData && tableData.rows.length > 0 ? (
                  <div className="data-table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {tableData.columns.map(col => (
                            <th key={col}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {tableData.rows.map((row, rowIndex) => (
                          <>
                            <tr
                              key={rowIndex}
                              className="clickable"
                              onClick={() => setExpandedRow(expandedRow === rowIndex ? null : rowIndex)}
                            >
                              {row.map((cell, cellIndex) => (
                                <td key={cellIndex} title={String(cell)}>
                                  {formatCellValue(cell)}
                                </td>
                              ))}
                            </tr>
                            {expandedRow === rowIndex && (
                              <tr key={`${rowIndex}-expanded`} className="expanded-row">
                                <td colSpan={tableData.columns.length}>
                                  <div className="expanded-content">
                                    {tableData.columns.map((col, i) => (
                                      <div key={col} className="expanded-field">
                                        <strong>{col}:</strong>
                                        {isJsonColumn(col) && row[i] ? (
                                          <pre>{formatJson(String(row[i]))}</pre>
                                        ) : (
                                          <span>{String(row[i] ?? 'NULL')}</span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : tableData ? (
                  <p className="no-data">No data in this table</p>
                ) : loading ? (
                  <p>Loading data...</p>
                ) : null}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default DataView

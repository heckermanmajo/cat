import { useState, useEffect } from 'react'
import './ActivityHeatmap.css'

interface DailyActivity {
  date: string
  dayName: string
  count: number
}

interface ActivityData {
  heatmap: number[][] // 7 Tage x 24 Stunden
  dailyBreakdown: DailyActivity[]
  total: number
}

interface ActivityHeatmapProps {
  selectionId?: number
  communityIds?: string[]
}

const TIMEZONES = [
  { value: 'Europe/Berlin', label: 'Berlin (CET/CEST)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'America/New_York', label: 'New York (EST/EDT)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (PST/PDT)' },
  { value: 'UTC', label: 'UTC' },
]

const DAY_NAMES = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

export function ActivityHeatmap({ selectionId, communityIds }: ActivityHeatmapProps) {
  const [timezone, setTimezone] = useState('Europe/Berlin')
  const [data, setData] = useState<ActivityData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [timezone, selectionId, communityIds])

  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        timezone,
        days: '7'
      })

      if (communityIds && communityIds.length > 0) {
        params.append('communityIds', communityIds.join(','))
      }

      const res = await fetch(`http://localhost:3000/api/activity?${params}`)

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const activityData = await res.json()
      setData(activityData)
    } catch (err) {
      console.error('Error loading activity data:', err)
      setError('Fehler beim Laden der Aktivitaetsdaten')
    } finally {
      setLoading(false)
    }
  }

  const handleTimezoneChange = (tz: string) => {
    setTimezone(tz)
  }

  // Max-Wert fuer Skalierung berechnen
  const getMaxValue = (): number => {
    if (!data) return 0
    let max = 0
    for (const row of data.heatmap) {
      for (const val of row) {
        if (val > max) max = val
      }
    }
    return max
  }

  const getOpacity = (value: number): number => {
    const maxValue = getMaxValue()
    if (maxValue === 0 || value === 0) return 0.1
    return 0.15 + (value / maxValue) * 0.85
  }

  const getMaxDayCount = (): number => {
    if (!data || !data.dailyBreakdown.length) return 0
    return Math.max(...data.dailyBreakdown.map(d => d.count))
  }

  if (loading) {
    return (
      <div className="activity-heatmap">
        <div className="loading-state">Lade Aktivitaetsdaten...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="activity-heatmap">
        <div className="error-state">{error}</div>
      </div>
    )
  }

  if (!data || data.total === 0) {
    return (
      <div className="activity-heatmap">
        <div className="empty-state">
          Keine Aktivitaetsdaten vorhanden.
          <br />
          <small>Stelle sicher, dass Members-Fetches durchgefuehrt wurden.</small>
        </div>
      </div>
    )
  }

  const maxDayCount = getMaxDayCount()

  return (
    <div className="activity-heatmap">
      {/* Header mit Timezone */}
      <div className="activity-header">
        <span className="activity-title">Online-Aktivitaet (7 Tage)</span>
        <select
          value={timezone}
          onChange={(e) => handleTimezoneChange(e.target.value)}
          className="timezone-select"
        >
          {TIMEZONES.map(tz => (
            <option key={tz.value} value={tz.value}>{tz.label}</option>
          ))}
        </select>
      </div>

      {/* Stats */}
      <div className="activity-stats">
        <span className="stats-number">{data.total}</span>
        <span className="stats-label">User-Tag Kombinationen</span>
      </div>

      {/* Heatmap Grid */}
      <div className="heatmap-section">
        <div className="heatmap-label">Woechentliche Heatmap</div>
        <div className="heatmap-grid">
          {/* Header-Zeile mit Tagen */}
          <div className="heatmap-corner"></div>
          {DAY_NAMES.map(day => (
            <div key={day} className="heatmap-day-header">{day}</div>
          ))}

          {/* Stunden-Zeilen */}
          {Array.from({ length: 24 }, (_, hour) => (
            <div key={`row-${hour}`} className="heatmap-row">
              <div className="heatmap-hour-label">
                {hour.toString().padStart(2, '0')}
              </div>
              {Array.from({ length: 7 }, (_, day) => {
                const value = data.heatmap[day]?.[hour] || 0
                return (
                  <div
                    key={`cell-${day}-${hour}`}
                    className="heatmap-cell"
                    style={{ opacity: getOpacity(value) }}
                    title={`${DAY_NAMES[day]} ${hour}:00 - ${value} User`}
                  />
                )
              })}
            </div>
          ))}
        </div>

        {/* Legende */}
        <div className="heatmap-legend">
          <span>Weniger</span>
          <div className="legend-gradient" />
          <span>Mehr</span>
        </div>
      </div>

      {/* Daily Breakdown */}
      <div className="daily-breakdown">
        <div className="breakdown-label">Taegliche Uebersicht</div>
        {data.dailyBreakdown.length === 0 ? (
          <div className="no-data">Keine Daten fuer diesen Zeitraum</div>
        ) : (
          data.dailyBreakdown.map(day => (
            <div key={day.date} className="breakdown-row">
              <div className="breakdown-date">
                <span className="day-name">{day.dayName}</span>
                <span className="date-value">{day.date}</span>
              </div>
              <div className="breakdown-bar-container">
                <div
                  className="breakdown-bar"
                  style={{ width: maxDayCount > 0 ? `${(day.count / maxDayCount) * 100}%` : '0%' }}
                />
              </div>
              <div className="breakdown-count">{day.count}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default ActivityHeatmap

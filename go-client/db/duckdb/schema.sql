-- Raw Data Layer (DuckDB)
-- Speichert alle Rohdaten von Fetches als JSON
-- Append-only / versioniert (mehrere Fetches pro Entität erlaubt)

CREATE TABLE IF NOT EXISTS raw_fetches (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source TEXT DEFAULT 'skool',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index für schnelle Abfragen nach Entität
CREATE INDEX IF NOT EXISTS idx_raw_fetches_entity
ON raw_fetches(entity_type, entity_id, fetched_at DESC);

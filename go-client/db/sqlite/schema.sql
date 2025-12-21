-- App Data Layer (SQLite)
-- Speichert alle anwendungsspezifischen Daten

-- App Settings (Key-Value)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- UI State (Tab-Auswahl, letzte Ansicht, etc.)
CREATE TABLE IF NOT EXISTS ui_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saved queries (Filter, Suchen, Quicklinks)
CREATE TABLE IF NOT EXISTS saved_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    query_type TEXT NOT NULL,
    query_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- License info
CREATE TABLE IF NOT EXISTS license (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    license_key TEXT,
    status TEXT DEFAULT 'inactive',
    expires_at TIMESTAMP,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analysis reports (Snapshots)
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync log (Protokoll der Extension-Syncs)
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,
    entity_count INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Application logs (Zentrale Logging-Tabelle)
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL CHECK(level IN ('debug', 'info', 'warn', 'error')),
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index für schnelle Log-Abfragen
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at DESC);

-- === Chat, Selections & Report System ===

-- Chats (Konversationen mit AI)
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Neuer Chat',
    report_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE SET NULL
);

-- Messages (Einzelne Nachrichten im Chat)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

-- Selections (Persistierte Datenabfragen)
CREATE TABLE IF NOT EXISTS selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'Neue Selektion',
    output_type TEXT NOT NULL CHECK(output_type IN ('community', 'member', 'post')),
    filters_json TEXT NOT NULL DEFAULT '{}',
    result_count INTEGER DEFAULT 0,
    result_ids_json TEXT DEFAULT '[]',
    created_by TEXT NOT NULL CHECK(created_by IN ('user', 'assistant')),
    message_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
);

-- Report Blocks (Bausteine eines Reports)
CREATE TABLE IF NOT EXISTS report_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    block_type TEXT NOT NULL CHECK(block_type IN ('text', 'selection')),
    position INTEGER NOT NULL DEFAULT 0,
    content TEXT,
    selection_id INTEGER,
    view_type TEXT DEFAULT 'list',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
    FOREIGN KEY (selection_id) REFERENCES selections(id) ON DELETE SET NULL
);

-- Indices für Chat-System
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_selections_message_id ON selections(message_id);
CREATE INDEX IF NOT EXISTS idx_selections_output_type ON selections(output_type);
CREATE INDEX IF NOT EXISTS idx_report_blocks_report_id ON report_blocks(report_id);
CREATE INDEX IF NOT EXISTS idx_report_blocks_position ON report_blocks(report_id, position);

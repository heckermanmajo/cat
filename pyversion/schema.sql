-- CatKnows SQLite Schema (vereinigt aus DuckDB + SQLite)

-- ============================================
-- RAW DATA (ehemals DuckDB)
-- ============================================

CREATE TABLE IF NOT EXISTS raw_fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,      -- about_page, members, community_page, profile, post_details, likes
    entity_id TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source TEXT DEFAULT 'skool',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_fetches_entity
ON raw_fetches(entity_type, entity_id, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_fetches_type
ON raw_fetches(entity_type);

-- ============================================
-- APP DATA
-- ============================================

-- Settings (Key-Value)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Logs
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL CHECK(level IN ('debug', 'info', 'warn', 'error')),
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at DESC);

-- Sync Log
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,
    entity_count INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- CHAT SYSTEM
-- ============================================

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Neuer Chat',
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);

-- ============================================
-- SELECTIONS
-- ============================================

CREATE TABLE IF NOT EXISTS selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'Neue Selektion',
    output_type TEXT NOT NULL CHECK(output_type IN ('community', 'member', 'post')),
    filters_json TEXT NOT NULL DEFAULT '{}',
    result_count INTEGER DEFAULT 0,
    result_ids_json TEXT DEFAULT '[]',
    created_by TEXT NOT NULL CHECK(created_by IN ('user', 'assistant')),
    message_id INTEGER,
    parent_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_id) REFERENCES selections(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_selections_output_type ON selections(output_type);

-- ============================================
-- PROMPT TEMPLATES
-- ============================================

CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'Allgemein',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- EXTRACTED ENTITIES (aus raw_fetches extrahiert)
-- ============================================

-- Members (extrahiert aus entity_type='members')
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,              -- User-ID von Skool
    name TEXT NOT NULL,
    slug TEXT,
    picture TEXT,
    community_id TEXT NOT NULL,
    role TEXT DEFAULT 'member',       -- admin, group-moderator, member, owner
    is_owner INTEGER DEFAULT 0,
    joined_at TEXT,                   -- YYYY-MM-DD
    last_online TEXT,
    post_count INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    raw_fetch_id INTEGER,             -- Referenz zum Ursprungs-Fetch
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_fetch_id) REFERENCES raw_fetches(id)
);

CREATE INDEX IF NOT EXISTS idx_members_community ON members(community_id);
CREATE INDEX IF NOT EXISTS idx_members_role ON members(role);
CREATE INDEX IF NOT EXISTS idx_members_level ON members(level);

-- Posts (extrahiert aus entity_type='community_page', 'post_details')
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,              -- Post-ID von Skool
    title TEXT,
    content TEXT,
    author_id TEXT,
    author_name TEXT,
    community_id TEXT NOT NULL,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    created_at TEXT,                  -- Original-Timestamp
    raw_fetch_id INTEGER,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_fetch_id) REFERENCES raw_fetches(id)
);

CREATE INDEX IF NOT EXISTS idx_posts_community ON posts(community_id);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_likes ON posts(likes);

-- Communities (extrahiert aus entity_type='about_page', 'community_page', 'members')
CREATE TABLE IF NOT EXISTS communities (
    id TEXT PRIMARY KEY,              -- Community-ID (UUID)
    name TEXT NOT NULL,
    slug TEXT,
    description TEXT,
    member_count INTEGER DEFAULT 0,
    post_count INTEGER DEFAULT 0,
    picture TEXT,
    raw_fetch_id INTEGER,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_fetch_id) REFERENCES raw_fetches(id)
);

CREATE INDEX IF NOT EXISTS idx_communities_slug ON communities(slug);

-- ============================================
-- LICENSE
-- ============================================

CREATE TABLE IF NOT EXISTS license (
    id INTEGER PRIMARY KEY,
    license_key TEXT NOT NULL,
    valid_until DATE,
    features TEXT DEFAULT '[]',  -- JSON array
    last_validated TIMESTAMP,
    server_reachable INTEGER DEFAULT 1,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

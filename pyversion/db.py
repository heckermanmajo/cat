"""
Database Helpers - Zentrale Datenbankfunktionen
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import g

# Wird von app.py gesetzt
DB_PATH = None
DATA_DIR = None


def init_paths(data_dir: Path):
    """Initialisiert die Pfade (wird von app.py aufgerufen)"""
    global DB_PATH, DATA_DIR
    DATA_DIR = data_dir
    DB_PATH = data_dir / 'app.sqlite'


def get_db():
    """Gibt die Datenbankverbindung zurück (cached pro Request)"""
    if 'db' not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    """Schließt die Datenbankverbindung"""
    db = g.pop('db', None)
    if db:
        db.close()


def get_setting(key: str, default: str = '') -> str:
    """Liest ein Setting aus der Datenbank"""
    row = get_db().execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    """Speichert ein Setting in der Datenbank"""
    get_db().execute(
        'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
        (key, value, datetime.now())
    )
    get_db().commit()


def log(level: str, source: str, message: str, details: str = None):
    """Schreibt einen Log-Eintrag in die Datenbank"""
    get_db().execute(
        'INSERT INTO logs (level, source, message, details) VALUES (?, ?, ?, ?)',
        (level, source, message, details)
    )
    get_db().commit()


def get_latest_fetch(entity_type: str, entity_id: str):
    """Holt den neuesten Fetch für entity_type + entity_id"""
    row = get_db().execute('''
        SELECT raw_json, fetched_at FROM raw_fetches
        WHERE entity_type = ? AND entity_id = ?
        ORDER BY fetched_at DESC LIMIT 1
    ''', (entity_type, entity_id)).fetchone()
    return row


def get_latest_fetches_by_type(entity_type: str):
    """Holt neueste Fetches pro Entity-ID"""
    return get_db().execute('''
        WITH latest AS (
            SELECT entity_id, MAX(fetched_at) as max_fetched
            FROM raw_fetches WHERE entity_type = ?
            GROUP BY entity_id
        )
        SELECT r.* FROM raw_fetches r
        INNER JOIN latest l ON r.entity_id = l.entity_id AND r.fetched_at = l.max_fetched
        WHERE r.entity_type = ?
    ''', (entity_type, entity_type)).fetchall()

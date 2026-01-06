"""
Basis-Utilities für Datenmodelle
"""

from typing import Any, Dict, Optional
import sqlite3


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Konvertiert SQLite-Rows zu Dictionaries"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_nested(data: dict, *keys, default=None) -> Any:
    """
    Sicherer Zugriff auf verschachtelte Dict-Keys.

    Beispiel:
        get_nested(data, 'user', 'profile', 'name', default='Unknown')
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
        if data is None:
            return default
    return data


def parse_bool(value: Any) -> bool:
    """Konvertiert verschiedene Werte zu bool"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return False

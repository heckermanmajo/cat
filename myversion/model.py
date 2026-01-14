import sqlite3
import time
import json
from typing import TypeVar, Type, Any, get_type_hints
from flask import request, jsonify

T = TypeVar('T')
_conn: sqlite3.Connection = None
_batch_mode: bool = False

class Model:
    """
        GET    /api/configentry      → JSON array
        GET    /api/configentry/5    → JSON object
        POST   /api/configentry      → create
        PUT    /api/configentry/5    → update
        DELETE /api/configentry/5    → delete

        NOTE: this application runs locally with always one user;
              -> means no 'web related security risks'.
    """
    id: int = None
    created_at: int = 0
    updated_at: int = 0

    def __init__(self, data: dict[str, Any] = None):
        if data:
            for k, v in data.items():
                if hasattr(self, k): setattr(self, k, v)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self._props(self.__class__)}

    # =========================================================================
    # Database
    # =========================================================================
    @staticmethod
    def connect(db_path: str = 'app.db') -> sqlite3.Connection:
        global _conn
        if _conn is None:
            _conn = sqlite3.connect(db_path, check_same_thread=False)
            _conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return _conn

    @staticmethod
    def begin_batch():
        global _batch_mode
        _batch_mode = True

    @staticmethod
    def end_batch():
        global _batch_mode
        _batch_mode = False
        Model.connect().commit()

    @staticmethod
    def _props(cls: type) -> dict[str, str]:
        props = {}
        hints = get_type_hints(cls) if hasattr(cls, '__annotations__') else {}
        for name, typ in hints.items():
            if name.startswith('_'): continue
            sql_type = 'TEXT'
            if typ == int: sql_type = 'INTEGER'
            elif typ == float: sql_type = 'REAL'
            props[name] = sql_type
        return props

    @classmethod
    def get_tablename(cls) -> str: return cls.__name__.lower()

    @classmethod
    def update_table(cls) -> None:
        table = cls.__name__.lower()
        props = Model._props(cls)
        conn = Model.connect()
        cols = [f"{n} {t}" + (' PRIMARY KEY AUTOINCREMENT' if n == 'id' else '') for n, t in props.items()]
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(cols)})")
        for name, typ in props.items():
            try: conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
            except: pass
        conn.commit()

    def save(self) -> None:
        cls = self.__class__
        table = cls.__name__.lower()
        props = Model._props(cls)
        data = {k: getattr(self, k) for k in props if k != 'id'}
        conn = Model.connect()
        if self.id is None:
            self.created_at = int(time.time())
            data['created_at'] = self.created_at
            cols = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(data.values()))
            self.id = cur.lastrowid
        else:
            self.updated_at = int(time.time())
            data['updated_at'] = self.updated_at
            sets = ', '.join([f"{k} = ?" for k in data.keys()])
            conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(data.values()) + [self.id])
        if not _batch_mode:
            conn.commit()

    def delete(self) -> None:
        table = self.__class__.__name__.lower()
        conn = Model.connect()
        conn.execute(f"DELETE FROM {table} WHERE id = ?", [self.id])
        conn.commit()

    @classmethod
    def by_id(cls: Type[T], id: int) -> T | None:
        table = cls.__name__.lower()
        row = Model.connect().execute(f"SELECT * FROM {table} WHERE id = ?", [id]).fetchone()
        return cls(row) if row else None

    @classmethod
    def all(cls: Type[T], order: str = 'id DESC') -> list[T]:
        table = cls.__name__.lower()
        return cls.get_list(f"SELECT * FROM {table} ORDER BY {order}")

    @classmethod
    def get_list(cls: Type[T], sql: str, args: list = None) -> list[T]:
        rows = Model.connect().execute(sql, args or []).fetchall()
        return [cls(row) for row in rows]

    @classmethod
    def count(cls, where: str = '1=1', args: list = None) -> int:
        table = cls.__name__.lower()
        row = Model.connect().execute(f"SELECT COUNT(*) as c FROM {table} WHERE {where}", args or []).fetchone()
        return row['c']

    @staticmethod
    def query(sql: str, args: list = None) -> list[dict]:
        return Model.connect().execute(sql, args or []).fetchall()

    # =========================================================================
    # API Routes - register with Flask app
    # =========================================================================
    @classmethod
    def register(cls, app):
        name = cls.__name__.lower()
        cls.update_table()

        @app.route(f'/api/{name}', methods=['GET'], endpoint=f'{name}_all')
        def get_all():
            return jsonify([x.to_dict() for x in cls.all()])

        @app.route(f'/api/{name}/<int:id>', methods=['GET'], endpoint=f'{name}_one')
        def get_one(id):
            obj = cls.by_id(id)
            return jsonify(obj.to_dict()) if obj else ('Not found', 404)

        @app.route(f'/api/{name}', methods=['POST'], endpoint=f'{name}_create')
        def create():
            obj = cls(request.json)
            obj.save()
            return jsonify(obj.to_dict()), 201

        @app.route(f'/api/{name}/<int:id>', methods=['PUT'], endpoint=f'{name}_update')
        def update(id):
            obj = cls.by_id(id)
            if not obj: return 'Not found', 404
            for k, v in request.json.items():
                if hasattr(obj, k): setattr(obj, k, v)
            obj.save()
            return jsonify(obj.to_dict())

        @app.route(f'/api/{name}/<int:id>', methods=['DELETE'], endpoint=f'{name}_delete')
        def delete(id):
            obj = cls.by_id(id)
            if not obj: return 'Not found', 404
            obj.delete()
            return '', 204

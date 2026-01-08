"""
REST API - Alle /api/* Endpunkte
"""

import json
from datetime import datetime

from flask import Blueprint, request

from db import get_db, get_setting, set_setting, log, get_latest_fetches_by_type
from data import (
    get_posts, get_members, get_communities,
    get_communities_with_shared_members, get_entities_stats
)
from fetch_queue import (
    build_fetch_queue, extract_entities_from_fetch, reprocess_all_raw_fetches
)
from license import check_license, activate_license

bp = Blueprint('api', __name__)


# ============================================
# BASIC API
# ============================================

@bp.route('/hello')
def api_hello():
    return {'message': 'Hello from CatKnows!'}


@bp.route('/ping', methods=['POST'])
def api_ping():
    data = request.get_json()
    return {'message': 'Pong!', 'received': data.get('timestamp') if data else None}


# ============================================
# SYNC API (für Browser Extension)
# ============================================

@bp.route('/sync', methods=['POST'])
def api_sync():
    """Daten von Browser Extension empfangen"""
    data = request.get_json()
    entity_type = data.get('entityType', '')
    source = data.get('source', 'skool')
    items = data.get('data', [])

    if not isinstance(items, list):
        items = [items]

    db = get_db()
    count = 0
    inserted_ids = []

    for item in items:
        entity_id = item.get('id', '') if isinstance(item, dict) else ''
        raw_json = json.dumps(item)
        cursor = db.execute(
            'INSERT INTO raw_fetches (entity_type, entity_id, raw_json, source) VALUES (?, ?, ?, ?)',
            (entity_type, str(entity_id), raw_json, source)
        )
        inserted_ids.append((cursor.lastrowid, entity_id, raw_json))
        count += 1
    db.commit()

    for raw_fetch_id, entity_id, raw_json in inserted_ids:
        try:
            extract_entities_from_fetch(raw_fetch_id, entity_type, entity_id, raw_json)
        except Exception as e:
            log('error', 'extraction', f'Failed to extract from {entity_type}/{entity_id}: {str(e)}')

    log('info', 'sync', f'Received {count} {entity_type}')
    return {'status': 'ok', 'count': count}


@bp.route('/stats')
def api_stats():
    """Statistiken für Extension"""
    db = get_db()
    total = db.execute('SELECT COUNT(*) as c FROM raw_fetches').fetchone()['c']
    by_type = db.execute(
        'SELECT entity_type, COUNT(*) as c FROM raw_fetches GROUP BY entity_type'
    ).fetchall()
    return {
        'rawFetchCount': total,
        'fetchesByType': {row['entity_type']: row['c'] for row in by_type}
    }


@bp.route('/reprocess', methods=['POST'])
def api_reprocess():
    """Alle raw_fetches neu verarbeiten"""
    count = reprocess_all_raw_fetches()
    return {'status': 'ok', 'processed': count}


@bp.route('/entities/stats')
def api_entities_stats():
    """Statistiken über extrahierte Entities"""
    return get_entities_stats()


# ============================================
# FETCH QUEUE
# ============================================

@bp.route('/fetch-queue', methods=['GET', 'POST'])
def api_fetch_queue():
    """Fetch-Queue für Extension generieren"""
    community_ids = request.args.get('communityIds', get_setting('community_ids'))
    if not community_ids:
        return {'tasks': [], 'totalTasks': 0, 'generatedAt': datetime.now().isoformat()}

    communities = [c.strip() for c in community_ids.split(',') if c.strip()]
    return build_fetch_queue(communities)


# ============================================
# SETTINGS
# ============================================

@bp.route('/settings', methods=['GET', 'POST'])
def api_settings():
    """Settings API für Extension-Kompatibilität"""
    if request.method == 'POST':
        data = request.get_json()
        for key, value in data.items():
            set_setting(key, value)
        return {'status': 'ok'}
    else:
        rows = get_db().execute('SELECT key, value FROM settings').fetchall()
        return {row['key']: row['value'] for row in rows}


@bp.route('/setting')
def api_setting():
    """Einzelnes Setting lesen"""
    key = request.args.get('key', '')
    default = request.args.get('default', '')
    return {'key': key, 'value': get_setting(key, default)}


# ============================================
# LOGS
# ============================================

@bp.route('/logs', methods=['GET', 'POST', 'DELETE'])
def api_logs():
    """Logs API"""
    if request.method == 'POST':
        data = request.get_json()
        log(
            data.get('level', 'info'),
            data.get('source', 'api'),
            data.get('message', ''),
            data.get('details')
        )
        return {'status': 'ok'}
    elif request.method == 'DELETE':
        get_db().execute('DELETE FROM logs')
        get_db().commit()
        return {'status': 'ok'}
    else:
        level = request.args.get('level', '')
        limit = int(request.args.get('limit', 100))

        query = 'SELECT * FROM logs WHERE 1=1'
        params = []
        if level:
            query += ' AND level = ?'
            params.append(level)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        logs = get_db().execute(query, params).fetchall()
        return {'logs': [dict(l) for l in logs]}


# ============================================
# DATA / FETCHES
# ============================================

@bp.route('/data/latest')
def api_data_latest():
    """Neueste Daten pro Entity-Typ"""
    entity_type = request.args.get('type', '')

    if entity_type:
        fetches = get_latest_fetches_by_type(entity_type)
    else:
        types = get_db().execute('SELECT DISTINCT entity_type FROM raw_fetches').fetchall()
        fetches = []
        for t in types:
            fetches.extend(get_latest_fetches_by_type(t['entity_type']))

    return {'data': [dict(f) for f in fetches]}


@bp.route('/fetches')
def api_fetches():
    """Alle Fetches durchsuchen"""
    entity_type = request.args.get('type', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = 'SELECT * FROM raw_fetches WHERE 1=1'
    params = []
    if entity_type:
        query += ' AND entity_type = ?'
        params.append(entity_type)
    query += ' ORDER BY fetched_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    fetches = get_db().execute(query, params).fetchall()
    total = get_db().execute(
        'SELECT COUNT(*) as c FROM raw_fetches' + (' WHERE entity_type = ?' if entity_type else ''),
        [entity_type] if entity_type else []
    ).fetchone()['c']

    return {'fetches': [dict(f) for f in fetches], 'total': total}


# ============================================
# LICENSE
# ============================================

@bp.route('/license', methods=['GET'])
def api_license_status():
    """Aktuellen Lizenz-Status abrufen"""
    return check_license(get_db())


# ============================================
# PROMPT TEMPLATES
# ============================================

@bp.route('/prompt-templates', methods=['GET', 'POST'])
def api_prompt_templates():
    """Prompt Templates API"""
    if request.method == 'POST':
        data = request.get_json()
        db = get_db()
        cursor = db.execute(
            'INSERT INTO prompt_templates (name, content, description, category) VALUES (?, ?, ?, ?)',
            (
                data.get('name', 'Neues Template'),
                data.get('content', ''),
                data.get('description', ''),
                data.get('category', 'custom')
            )
        )
        db.commit()
        return {'status': 'ok', 'id': cursor.lastrowid}
    else:
        templates = get_db().execute(
            'SELECT * FROM prompt_templates ORDER BY category, name'
        ).fetchall()
        return {'templates': [dict(t) for t in templates]}


@bp.route('/prompt-template', methods=['GET', 'PUT', 'DELETE'])
def api_prompt_template():
    """Einzelnes Prompt Template"""
    template_id = request.args.get('id', type=int)
    if not template_id:
        return {'error': 'ID required'}, 400

    db = get_db()

    if request.method == 'DELETE':
        db.execute('DELETE FROM prompt_templates WHERE id = ?', (template_id,))
        db.commit()
        return {'status': 'ok'}

    elif request.method == 'PUT':
        data = request.get_json()
        db.execute('''
            UPDATE prompt_templates
            SET name = ?, content = ?, description = ?, category = ?
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('content'),
            data.get('description'),
            data.get('category'),
            template_id
        ))
        db.commit()
        return {'status': 'ok'}

    else:
        template = db.execute(
            'SELECT * FROM prompt_templates WHERE id = ?', (template_id,)
        ).fetchone()
        if not template:
            return {'error': 'Template not found'}, 404
        return {'template': dict(template)}


# ============================================
# SELECTIONS
# ============================================

@bp.route('/selections', methods=['GET', 'POST'])
def api_selections():
    """Selections API"""
    if request.method == 'POST':
        data = request.get_json()
        db = get_db()
        cursor = db.execute('''
            INSERT INTO selections (name, output_type, filters_json, created_by)
            VALUES (?, ?, ?, ?)
        ''', (
            data.get('name', 'Neue Selektion'),
            data.get('output_type', 'post'),
            json.dumps(data.get('filters', {})),
            data.get('created_by', 'user')
        ))
        db.commit()
        return {'status': 'ok', 'id': cursor.lastrowid}
    else:
        selections = get_db().execute(
            'SELECT * FROM selections ORDER BY created_at DESC'
        ).fetchall()
        return {'selections': [dict(s) for s in selections]}


@bp.route('/selection', methods=['GET', 'PUT', 'DELETE'])
def api_selection():
    """Einzelne Selection"""
    selection_id = request.args.get('id', type=int)
    if not selection_id:
        return {'error': 'ID required'}, 400

    db = get_db()

    if request.method == 'DELETE':
        db.execute('DELETE FROM selections WHERE id = ?', (selection_id,))
        db.commit()
        return {'status': 'ok'}

    elif request.method == 'PUT':
        data = request.get_json()
        db.execute('''
            UPDATE selections
            SET name = ?, output_type = ?, filters_json = ?, updated_at = ?
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('output_type'),
            json.dumps(data.get('filters', {})),
            datetime.now(),
            selection_id
        ))
        db.commit()
        return {'status': 'ok'}

    else:
        selection = db.execute(
            'SELECT * FROM selections WHERE id = ?', (selection_id,)
        ).fetchone()
        if not selection:
            return {'error': 'Selection not found'}, 404
        return {'selection': dict(selection)}


@bp.route('/selection/execute', methods=['GET'])
def api_execute_selection():
    """Selection ausführen"""
    selection_id = request.args.get('id', type=int)
    if not selection_id:
        return {'error': 'ID required'}, 400

    selection = get_db().execute(
        'SELECT * FROM selections WHERE id = ?', (selection_id,)
    ).fetchone()
    if not selection:
        return {'error': 'Selection not found'}, 404

    filters = json.loads(selection['filters_json'])
    output_type = selection['output_type']

    if output_type == 'post':
        results = get_posts(filters)
    elif output_type == 'member':
        results = get_members(filters)
    elif output_type == 'community':
        results = get_communities_with_shared_members(filters)
    else:
        results = []

    result_ids = [r.get('id', '') for r in results]
    get_db().execute('''
        UPDATE selections
        SET result_count = ?, result_ids_json = ?, updated_at = ?
        WHERE id = ?
    ''', (len(results), json.dumps(result_ids), datetime.now(), selection_id))
    get_db().commit()

    return {
        'selection': dict(selection),
        'results': results[:100],
        'total': len(results)
    }


@bp.route('/selection/duplicate', methods=['POST'])
def api_duplicate_selection():
    """Selection duplizieren"""
    selection_id = request.args.get('id', type=int)
    if not selection_id:
        return {'error': 'ID required'}, 400

    db = get_db()
    original = db.execute(
        'SELECT * FROM selections WHERE id = ?', (selection_id,)
    ).fetchone()
    if not original:
        return {'error': 'Selection not found'}, 404

    cursor = db.execute('''
        INSERT INTO selections (name, output_type, filters_json, created_by, parent_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        f"{original['name']} (Kopie)",
        original['output_type'],
        original['filters_json'],
        'user',
        selection_id
    ))
    db.commit()
    return {'status': 'ok', 'id': cursor.lastrowid}


# ============================================
# SCHEMA / TABLE DATA
# ============================================

@bp.route('/schema', methods=['GET'])
def api_schema():
    """Gibt alle Tabellen mit Spalten zurück"""
    db = get_db()
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = []
    for row in cursor:
        table_name = row['name']
        cols = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        tables.append({
            "name": table_name,
            "columns": [{"name": c['name'], "type": c['type'], "notnull": c['notnull']} for c in cols]
        })
    return {'tables': tables}


@bp.route('/table-data', methods=['GET'])
def api_table_data():
    """Query beliebige Tabelle mit Filtern"""
    table = request.args.get('table')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    allowed_tables = ['raw_fetches', 'logs', 'settings', 'chats', 'messages',
                      'selections', 'prompt_templates', 'sync_log']
    if table not in allowed_tables:
        return {'error': f'Invalid table. Allowed: {allowed_tables}'}, 400

    db = get_db()
    data = db.execute(
        f"SELECT * FROM {table} LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()

    total = db.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()['c']

    return {
        'table': table,
        'data': [dict(row) for row in data],
        'total': total,
        'limit': limit,
        'offset': offset
    }


# ============================================
# ACTIVITY / CONNECTIONS
# ============================================

@bp.route('/activity', methods=['GET'])
def api_activity():
    """Zeitreihe der Aktivität"""
    community_id = request.args.get('community_id', '')
    days = request.args.get('days', 30, type=int)
    entity_type = request.args.get('type', '')

    db = get_db()

    query = '''
        SELECT
            date(fetched_at) as day,
            entity_type,
            COUNT(*) as count
        FROM raw_fetches
        WHERE fetched_at > datetime('now', ?)
    '''
    params = [f'-{days} days']

    if entity_type:
        query += ' AND entity_type = ?'
        params.append(entity_type)

    if community_id:
        query += ' AND entity_id LIKE ?'
        params.append(f'{community_id}%')

    query += ' GROUP BY date(fetched_at), entity_type ORDER BY day'

    data = db.execute(query, params).fetchall()

    timeline = {}
    for row in data:
        day = row['day']
        if day not in timeline:
            timeline[day] = {'date': day, 'total': 0}
        timeline[day][row['entity_type']] = row['count']
        timeline[day]['total'] += row['count']

    return {
        'timeline': sorted(timeline.values(), key=lambda x: x['date']),
        'days': days,
        'community_id': community_id
    }


@bp.route('/connections', methods=['GET'])
def api_connections():
    """Netzwerk der Member-Interaktionen"""
    community_id = request.args.get('community_id', '')

    filters = {}
    if community_id:
        filters['community_ids'] = [community_id]

    members = get_members(filters)
    posts = get_posts(filters)

    nodes = []
    member_ids = set()
    for m in members:
        if m['id'] not in member_ids:
            member_ids.add(m['id'])
            nodes.append({
                'id': m['id'],
                'name': m['name'],
                'posts': m.get('post_count', 0),
                'level': m.get('level', 0),
                'role': m.get('role', 'member')
            })

    edges = []
    author_posts = {}
    for p in posts:
        aid = p.get('author_id')
        if aid:
            if aid not in author_posts:
                author_posts[aid] = 0
            author_posts[aid] += 1

    active_authors = [aid for aid, count in author_posts.items() if count >= 2]
    for i, a1 in enumerate(active_authors):
        for a2 in active_authors[i+1:]:
            edges.append({
                'from': a1,
                'to': a2,
                'weight': min(author_posts.get(a1, 0), author_posts.get(a2, 0))
            })

    return {
        'nodes': nodes[:100],
        'edges': edges[:200],
        'total_nodes': len(nodes),
        'total_edges': len(edges)
    }

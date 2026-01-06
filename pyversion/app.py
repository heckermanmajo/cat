#!/usr/bin/env python3
"""
CatKnows - Local Skool Analytics
Single-file Flask application with htmx
"""

import json
import os
import re
import sqlite3
import ssl
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from threading import Timer
from urllib.request import Request, urlopen

import certifi
from flask import Flask, Response, g, render_template, request, stream_with_context

# Importiere Data Models
from models import Member, Post, Community
from license import check_license, activate_license

# SSL-Kontext mit certifi-Zertifikaten
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# ============================================
# CONFIG
# ============================================

def get_data_dir():
    """Datenverzeichnis neben dem Binary"""
    if getattr(sys, 'frozen', False):
        # Nuitka compiled
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / 'catknows_data'

DATA_DIR = get_data_dir()
DB_PATH = DATA_DIR / 'app.sqlite'
DEFAULT_PORT = 3000

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ============================================
# CORS (für Browser Extension)
# ============================================

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS preflight requests"""
    return '', 204

# ============================================
# DATABASE
# ============================================

def get_db():
    if 'db' not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    """Schema initialisieren"""
    with app.app_context():
        db = get_db()
        schema_path = Path(__file__).parent / 'schema.sql'
        if schema_path.exists():
            db.executescript(schema_path.read_text())
            db.commit()

# ============================================
# HELPERS
# ============================================

def get_setting(key, default=''):
    row = get_db().execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default

def set_setting(key, value):
    get_db().execute(
        'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
        (key, value, datetime.now())
    )
    get_db().commit()

def log(level, source, message, details=None):
    get_db().execute(
        'INSERT INTO logs (level, source, message, details) VALUES (?, ?, ?, ?)',
        (level, source, message, details)
    )
    get_db().commit()

# ============================================
# ROUTES - PAGES
# ============================================

@app.route('/')
def index():
    """Hauptseite - Chat View"""
    chats = get_db().execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    return render_template('chat.html', chats=chats)

@app.route('/settings')
def settings():
    """Settings View"""
    license_status = check_license(get_db())
    return render_template('settings.html',
        tab=request.args.get('tab', 'settings'),
        community_ids=get_setting('community_ids'),
        openai_api_key=get_setting('openai_api_key'),
        license=license_status
    )


@app.route('/filter')
def filter_page():
    """Filter View"""
    communities = get_available_communities()
    return render_template('filter.html',
        output_type='post',
        communities=communities
    )


def get_available_communities():
    """Holt alle Communities aus der communities-Tabelle mit ID und Name"""
    rows = get_db().execute('''
        SELECT id, name, slug FROM communities
        ORDER BY name
    ''').fetchall()
    # Gib Liste von Dictionaries zurück mit id und name
    return [{'id': r['id'], 'name': r['name'] or r['slug'] or r['id']} for r in rows]


# ============================================
# ROUTES - API (für Browser Extension)
# ============================================

@app.route('/api/hello')
def api_hello():
    return {'message': 'Hello from CatKnows!'}

@app.route('/api/ping', methods=['POST'])
def api_ping():
    data = request.get_json()
    return {'message': 'Pong!', 'received': data.get('timestamp') if data else None}

@app.route('/api/sync', methods=['POST'])
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
    inserted_ids = []  # Speichere IDs für Extraktion

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

    # Extrahiere Entities aus den neuen raw_fetches
    for raw_fetch_id, entity_id, raw_json in inserted_ids:
        try:
            extract_entities_from_fetch(raw_fetch_id, entity_type, entity_id, raw_json)
        except Exception as e:
            log('error', 'extraction', f'Failed to extract from {entity_type}/{entity_id}: {str(e)}')

    log('info', 'sync', f'Received {count} {entity_type}')
    return {'status': 'ok', 'count': count}

@app.route('/api/stats')
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

# ============================================
# ENTITY EXTRACTION (raw_json -> strukturierte Tabellen)
# ============================================

def extract_entities_from_fetch(raw_fetch_id: int, entity_type: str, entity_id: str, raw_json: str):
    """
    Extrahiert strukturierte Entities aus einem raw_fetch und speichert sie.
    Wird automatisch nach jedem /api/sync aufgerufen.
    """
    db = get_db()

    if entity_type == 'members':
        # Extrahiere Members (mit entity_id als Fallback für community_id)
        members = Member.extract_from_raw_json(raw_json, raw_fetch_id, entity_id)
        for member in members:
            db.execute(Member.upsert_sql(), member.to_db_row())

        # Extrahiere auch Community-Info aus members-Fetch
        community = Community.extract_from_members_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    elif entity_type == 'community_page':
        # Extrahiere Posts (mit entity_id für community_id)
        posts = Post.extract_from_community_page(raw_json, raw_fetch_id, entity_id)
        for post in posts:
            db.execute(Post.upsert_sql(), post.to_db_row())

        # Extrahiere auch Community-Info
        community = Community.extract_from_community_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    elif entity_type == 'post_details':
        # Extrahiere einzelnen Post mit Details (mit entity_id für community_id)
        post = Post.extract_from_post_details(raw_json, raw_fetch_id, entity_id)
        if post:
            db.execute(Post.upsert_sql(), post.to_db_row())

    elif entity_type == 'about_page':
        # Extrahiere Community-Info
        community = Community.extract_from_about_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    db.commit()


def _upsert_community(db, community: Community):
    """
    Upsert für Community mit Merge-Logik:
    Wenn Community schon existiert, merge die besseren Werte.
    """
    existing_row = db.execute(
        'SELECT * FROM communities WHERE id = ?',
        (community.id,)
    ).fetchone()

    if existing_row:
        existing = Community.from_db_row(dict(existing_row))
        merged = community.merge_with(existing)
        db.execute(Community.upsert_sql(), merged.to_db_row())
    else:
        db.execute(Community.upsert_sql(), community.to_db_row())


def reprocess_all_raw_fetches():
    """
    Verarbeitet alle raw_fetches neu und extrahiert Entities.
    Nützlich nach Schema-Updates oder bei Datenproblemen.
    """
    db = get_db()

    # Lösche alle extrahierten Entities
    db.execute('DELETE FROM members')
    db.execute('DELETE FROM posts')
    db.execute('DELETE FROM communities')
    db.commit()

    # Hole alle raw_fetches
    rows = db.execute(
        'SELECT id, entity_type, entity_id, raw_json FROM raw_fetches ORDER BY fetched_at'
    ).fetchall()

    processed = 0
    for row in rows:
        extract_entities_from_fetch(
            raw_fetch_id=row['id'],
            entity_type=row['entity_type'],
            entity_id=row['entity_id'],
            raw_json=row['raw_json']
        )
        processed += 1

    log('info', 'reprocess', f'Reprocessed {processed} raw_fetches')
    return processed


@app.route('/api/reprocess', methods=['POST'])
def api_reprocess():
    """Alle raw_fetches neu verarbeiten"""
    count = reprocess_all_raw_fetches()
    return {'status': 'ok', 'processed': count}


@app.route('/api/entities/stats')
def api_entities_stats():
    """Statistiken über extrahierte Entities"""
    db = get_db()
    return {
        'members': db.execute('SELECT COUNT(*) as c FROM members').fetchone()['c'],
        'posts': db.execute('SELECT COUNT(*) as c FROM posts').fetchone()['c'],
        'communities': db.execute('SELECT COUNT(*) as c FROM communities').fetchone()['c']
    }


# ============================================
# FETCH QUEUE BUILDER (wie Go-Version)
# ============================================

# Prioritäten (niedrigere Werte = höhere Priorität)
PRIORITY_CRITICAL = 0  # Initiale Fetches, ohne die nichts geht
PRIORITY_HIGH = 1      # Primäre Fetches (Members, Posts)
PRIORITY_MEDIUM = 2    # Sekundäre Fetches (Details, Likes)
PRIORITY_LOW = 3       # Tertiäre Fetches (Profile)
PRIORITY_LOWEST = 4    # Erweiterte Fetches (Shared Communities)

# Refresh-Interval in Sekunden (24 Stunden)
REFRESH_INTERVAL = 86400

# Config
FETCH_POST_LIKES = True
FETCH_POST_COMMENTS = True  # via post_details
FETCH_MEMBER_PROFILES = True


def get_latest_fetch(entity_type: str, entity_id: str):
    """Holt den neuesten Fetch für entity_type + entity_id"""
    row = get_db().execute('''
        SELECT raw_json, fetched_at FROM raw_fetches
        WHERE entity_type = ? AND entity_id = ?
        ORDER BY fetched_at DESC LIMIT 1
    ''', (entity_type, entity_id)).fetchone()
    return row


def parse_fetched_at(fetched_at_str) -> datetime | None:
    """Parst fetched_at String zu datetime"""
    if not fetched_at_str:
        return None
    try:
        # SQLite TIMESTAMP format
        return datetime.fromisoformat(str(fetched_at_str).replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def needs_refresh(fetched_at: datetime | None) -> bool:
    """Prüft ob Refresh nötig ist"""
    if fetched_at is None:
        return True
    return (datetime.now() - fetched_at).total_seconds() > REFRESH_INTERVAL


def generate_task_id(fetch_type: str, community_id: str, suffix: str = '') -> str:
    """Generiert eine Task-ID"""
    task_id = f"{fetch_type}_{community_id}"
    if suffix:
        task_id += f"_{suffix}"
    return task_id


def extract_member_info(raw_json: str) -> tuple[list[dict], int]:
    """Extrahiert Member-Infos (ID + Slug) und Gesamtseitenzahl aus Members-JSON"""
    members = []
    total_pages = 1

    try:
        data = json.loads(raw_json)
        page_props = data.get('pageProps', {})

        # Gesamtseitenzahl
        if 'totalPages' in page_props:
            total_pages = int(page_props['totalPages'])

        # Member-Infos
        for user in page_props.get('users', []):
            user_id = user.get('id', '')
            slug = user.get('name', '')  # "name" ist der Slug in Skool
            if user_id:
                members.append({'id': user_id, 'slug': slug})

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return members, total_pages


def extract_post_ids(raw_json: str) -> list[str]:
    """Extrahiert Post-IDs aus Community-Page-JSON"""
    post_ids = []

    try:
        data = json.loads(raw_json)
        page_props = data.get('pageProps', {})

        for pt in page_props.get('postTrees', []):
            post = pt.get('post', {})
            post_id = post.get('id', '')
            if post_id:
                post_ids.append(post_id)

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return post_ids


def extract_group_id(raw_json: str) -> str:
    """Extrahiert die Skool Group-ID (UUID) aus Community-Page-JSON"""
    try:
        data = json.loads(raw_json)
        page_props = data.get('pageProps', {})

        # Try to get groupId from first post
        for pt in page_props.get('postTrees', []):
            post = pt.get('post', {})
            group_id = post.get('groupId', '')
            if group_id:
                return group_id

        # Fallback: pageProps.groupId
        if page_props.get('groupId'):
            return page_props['groupId']

        # Fallback: pageProps.group.id
        group = page_props.get('group', {})
        if group.get('id'):
            return group['id']

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return ''


def build_members_tasks(community_id: str) -> tuple[list[dict], list[str]]:
    """Erstellt Tasks für Members-Fetches und gibt neue Member-Slugs zurück"""
    tasks = []
    new_member_slugs = []

    # Prüfe ob Page 1 existiert
    page1_id = f"{community_id}_page_1"
    row = get_latest_fetch('members', page1_id)

    if row is None:
        # Noch nie gefetcht - CRITICAL Priority
        tasks.append({
            'id': generate_task_id('members', community_id, 'page_1'),
            'type': 'members',
            'priority': PRIORITY_CRITICAL,
            'communityId': community_id,
            'page': 1,
            'reason': 'Initiales Members-Fetch - noch keine Daten vorhanden'
        })
        return tasks, new_member_slugs

    raw_json = row['raw_json']
    fetched_at = parse_fetched_at(row['fetched_at'])
    refresh_needed = needs_refresh(fetched_at)

    if refresh_needed:
        tasks.append({
            'id': generate_task_id('members', community_id, 'page_1'),
            'type': 'members',
            'priority': PRIORITY_HIGH,
            'communityId': community_id,
            'page': 1,
            'reason': f"Members-Refresh fällig (letzter Fetch: {fetched_at.strftime('%Y-%m-%d %H:%M') if fetched_at else 'unbekannt'})",
            'lastFetchedAt': fetched_at.isoformat() if fetched_at else None
        })

    # Extrahiere Member-Infos und Seitenzahl
    existing_members, total_pages = extract_member_info(raw_json)

    # Identifiziere neue Members (die noch kein Profile haben)
    for member in existing_members:
        slug = member.get('slug', '')
        if not slug:
            continue
        entity_id = f"{community_id}_{slug}"
        profile_row = get_latest_fetch('profile', entity_id)
        if profile_row is None:
            # Profil noch nicht gefetcht
            new_member_slugs.append(slug)

    # Prüfe weitere Pages
    for page in range(2, total_pages + 1):
        page_id = f"{community_id}_page_{page}"
        page_row = get_latest_fetch('members', page_id)

        if page_row is None:
            tasks.append({
                'id': generate_task_id('members', community_id, f'page_{page}'),
                'type': 'members',
                'priority': PRIORITY_HIGH,
                'communityId': community_id,
                'page': page,
                'reason': f'Members Page {page} noch nicht gefetcht'
            })
        else:
            page_fetched_at = parse_fetched_at(page_row['fetched_at'])
            if refresh_needed or needs_refresh(page_fetched_at):
                tasks.append({
                    'id': generate_task_id('members', community_id, f'page_{page}'),
                    'type': 'members',
                    'priority': PRIORITY_HIGH,
                    'communityId': community_id,
                    'page': page,
                    'reason': f'Members Page {page} Refresh fällig',
                    'lastFetchedAt': page_fetched_at.isoformat() if page_fetched_at else None
                })

        # Extrahiere auch Members von anderen Pages
        if page_row:
            page_members, _ = extract_member_info(page_row['raw_json'])
            for member in page_members:
                slug = member.get('slug', '')
                if slug and slug not in new_member_slugs:
                    entity_id = f"{community_id}_{slug}"
                    profile_row = get_latest_fetch('profile', entity_id)
                    if profile_row is None:
                        new_member_slugs.append(slug)

    return tasks, new_member_slugs


def build_posts_tasks(community_id: str) -> tuple[list[dict], list[str]]:
    """Erstellt Tasks für Community-Page-Fetches und gibt neue Post-IDs zurück"""
    tasks = []
    new_post_ids = []

    # Prüfe ob Page 1 existiert
    page1_id = f"{community_id}_page_1"
    row = get_latest_fetch('community_page', page1_id)

    if row is None:
        # Noch nie gefetcht - CRITICAL Priority
        tasks.append({
            'id': generate_task_id('community_page', community_id, 'page_1'),
            'type': 'community_page',
            'priority': PRIORITY_CRITICAL,
            'communityId': community_id,
            'page': 1,
            'reason': 'Initiales Posts-Fetch - noch keine Daten vorhanden'
        })
        return tasks, new_post_ids

    raw_json = row['raw_json']
    fetched_at = parse_fetched_at(row['fetched_at'])
    refresh_needed = needs_refresh(fetched_at)

    if refresh_needed:
        tasks.append({
            'id': generate_task_id('community_page', community_id, 'page_1'),
            'type': 'community_page',
            'priority': PRIORITY_HIGH,
            'communityId': community_id,
            'page': 1,
            'reason': f"Posts-Refresh fällig (letzter Fetch: {fetched_at.strftime('%Y-%m-%d %H:%M') if fetched_at else 'unbekannt'})",
            'lastFetchedAt': fetched_at.isoformat() if fetched_at else None
        })

    # Extrahiere Post-IDs und identifiziere neue Posts
    existing_post_ids = extract_post_ids(raw_json)

    for post_id in existing_post_ids:
        entity_id = f"{community_id}_{post_id}"
        details_row = get_latest_fetch('post_details', entity_id)
        if details_row is None:
            # Post-Details noch nicht gefetcht
            new_post_ids.append(post_id)

    return tasks, new_post_ids


def build_post_details_tasks(community_id: str, post_id: str, group_id: str) -> list[dict]:
    """Erstellt einen Task für Post-Details (inkl. Kommentare)"""
    tasks = []
    entity_id = f"{community_id}_{post_id}"
    row = get_latest_fetch('post_details', entity_id)

    params = {}
    if group_id:
        params['groupId'] = group_id

    if row is None:
        tasks.append({
            'id': generate_task_id('post_details', community_id, post_id),
            'type': 'post_details',
            'priority': PRIORITY_MEDIUM,
            'communityId': community_id,
            'entityId': post_id,
            'params': params,
            'reason': 'Post-Details (Kommentare) noch nie gefetcht'
        })
    else:
        fetched_at = parse_fetched_at(row['fetched_at'])
        if needs_refresh(fetched_at):
            tasks.append({
                'id': generate_task_id('post_details', community_id, post_id),
                'type': 'post_details',
                'priority': PRIORITY_MEDIUM,
                'communityId': community_id,
                'entityId': post_id,
                'params': params,
                'reason': 'Post-Details Refresh fällig',
                'lastFetchedAt': fetched_at.isoformat() if fetched_at else None
            })

    return tasks


def build_likes_tasks(community_id: str, post_id: str, group_id: str) -> list[dict]:
    """Erstellt einen Task für Post-Likes"""
    tasks = []
    entity_id = f"{community_id}_post_{post_id}"
    row = get_latest_fetch('likes', entity_id)

    params = {'targetType': 'post'}
    if group_id:
        params['groupId'] = group_id

    if row is None:
        tasks.append({
            'id': generate_task_id('likes', community_id, f'post_{post_id}'),
            'type': 'likes',
            'priority': PRIORITY_MEDIUM,
            'communityId': community_id,
            'entityId': post_id,
            'params': params,
            'reason': 'Post-Likes noch nie gefetcht'
        })
    else:
        fetched_at = parse_fetched_at(row['fetched_at'])
        if needs_refresh(fetched_at):
            tasks.append({
                'id': generate_task_id('likes', community_id, f'post_{post_id}'),
                'type': 'likes',
                'priority': PRIORITY_MEDIUM,
                'communityId': community_id,
                'entityId': post_id,
                'params': params,
                'reason': 'Post-Likes Refresh fällig',
                'lastFetchedAt': fetched_at.isoformat() if fetched_at else None
            })

    return tasks


def build_profile_tasks(community_id: str, member_slug: str) -> list[dict]:
    """Erstellt einen Task für Member-Profile"""
    tasks = []
    entity_id = f"{community_id}_{member_slug}"
    row = get_latest_fetch('profile', entity_id)

    if row is None:
        tasks.append({
            'id': generate_task_id('profile', community_id, member_slug),
            'type': 'profile',
            'priority': PRIORITY_LOW,
            'communityId': community_id,
            'entityId': member_slug,  # Slug für /@slug.json URL
            'reason': 'Member-Profil noch nie gefetcht'
        })
    else:
        fetched_at = parse_fetched_at(row['fetched_at'])
        if needs_refresh(fetched_at):
            tasks.append({
                'id': generate_task_id('profile', community_id, member_slug),
                'type': 'profile',
                'priority': PRIORITY_LOW,
                'communityId': community_id,
                'entityId': member_slug,
                'reason': 'Member-Profil Refresh fällig',
                'lastFetchedAt': fetched_at.isoformat() if fetched_at else None
            })

    return tasks


def build_fetch_queue(community_ids: list[str]) -> dict:
    """
    Erstellt die Fetch-Queue nach der Hierarchie:
    1. PRIMÄR: Members + Community Page (Posts) - inkrementell mit Pagination
    2. SEKUNDÄR: Post Details (Kommentare) + Likes für neue Posts
    3. TERTIÄR: Profile für neue Members
    """
    tasks = []

    # Sammle alle neuen Post-IDs und Member-Slugs
    all_new_post_ids = {}      # postID -> communityID
    all_new_member_slugs = {}  # memberSlug -> communityID
    community_group_ids = {}   # communityID (slug) -> groupId (Skool UUID)

    for community_id in community_ids:
        # ========================================
        # PHASE 1: PRIMÄRE FETCHES (Members + Posts)
        # ========================================

        # 1a. Members Pages
        members_tasks, new_member_slugs = build_members_tasks(community_id)
        tasks.extend(members_tasks)
        for slug in new_member_slugs:
            all_new_member_slugs[slug] = community_id

        # 1b. Community Page (Posts)
        posts_tasks, new_post_ids = build_posts_tasks(community_id)
        tasks.extend(posts_tasks)
        for pid in new_post_ids:
            all_new_post_ids[pid] = community_id

        # Extrahiere groupId für api2.skool.com API-Aufrufe
        page1_id = f"{community_id}_page_1"
        row = get_latest_fetch('community_page', page1_id)
        if row:
            group_id = extract_group_id(row['raw_json'])
            if group_id:
                community_group_ids[community_id] = group_id

    # ========================================
    # PHASE 2: SEKUNDÄRE FETCHES (Post Details + Likes)
    # ========================================

    if FETCH_POST_COMMENTS:
        for post_id, community_id in all_new_post_ids.items():
            group_id = community_group_ids.get(community_id, '')
            tasks.extend(build_post_details_tasks(community_id, post_id, group_id))

    if FETCH_POST_LIKES:
        for post_id, community_id in all_new_post_ids.items():
            group_id = community_group_ids.get(community_id, '')
            tasks.extend(build_likes_tasks(community_id, post_id, group_id))

    # ========================================
    # PHASE 3: TERTIÄRE FETCHES (Member Profiles)
    # ========================================

    if FETCH_MEMBER_PROFILES:
        for member_slug, community_id in all_new_member_slugs.items():
            tasks.extend(build_profile_tasks(community_id, member_slug))

    # Nach Priorität sortieren (stabil)
    tasks.sort(key=lambda t: t['priority'])

    return {
        'tasks': tasks,
        'generatedAt': datetime.now().isoformat(),
        'totalTasks': len(tasks)
    }


@app.route('/api/fetch-queue', methods=['GET', 'POST'])
def api_fetch_queue():
    """Fetch-Queue für Extension generieren"""
    community_ids = request.args.get('communityIds', get_setting('community_ids'))
    if not community_ids:
        return {'tasks': [], 'totalTasks': 0, 'generatedAt': datetime.now().isoformat()}

    communities = [c.strip() for c in community_ids.split(',') if c.strip()]
    return build_fetch_queue(communities)

def build_fetch_url(entity_type, community):
    """URL für Fetch-Task bauen"""
    base = f'https://www.skool.com/{community}'
    urls = {
        'about_page': f'{base}/about',
        'members': f'{base}/members',
        'community_page': base,
    }
    return urls.get(entity_type, base)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Settings API für Extension-Kompatibilität"""
    if request.method == 'POST':
        data = request.get_json()
        for key, value in data.items():
            set_setting(key, value)
        return {'status': 'ok'}
    else:
        # Alle Settings zurückgeben
        rows = get_db().execute('SELECT key, value FROM settings').fetchall()
        return {row['key']: row['value'] for row in rows}

@app.route('/api/setting')
def api_setting():
    """Einzelnes Setting lesen"""
    key = request.args.get('key', '')
    default = request.args.get('default', '')
    return {'key': key, 'value': get_setting(key, default)}

@app.route('/api/logs', methods=['GET', 'POST', 'DELETE'])
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

@app.route('/api/data/latest')
def api_data_latest():
    """Neueste Daten pro Entity-Typ"""
    entity_type = request.args.get('type', '')

    if entity_type:
        fetches = get_latest_fetches_by_type(entity_type)
    else:
        # Alle Typen
        types = get_db().execute('SELECT DISTINCT entity_type FROM raw_fetches').fetchall()
        fetches = []
        for t in types:
            fetches.extend(get_latest_fetches_by_type(t['entity_type']))

    return {'data': [dict(f) for f in fetches]}

@app.route('/api/fetches')
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
# ROUTES - HTMX PARTIALS
# ============================================

@app.route('/htmx/settings', methods=['POST'])
def htmx_save_setting():
    """Setting speichern - gibt Toast zurück"""
    key = request.form.get('key')
    value = request.form.get('value', '')
    set_setting(key, value)
    return render_template('partials/toast.html', message='Gespeichert!', type='success')


# ============================================
# ROUTES - LICENSE
# ============================================

@app.route('/api/license', methods=['GET'])
def api_license_status():
    """Aktuellen Lizenz-Status abrufen"""
    return check_license(get_db())


@app.route('/htmx/license/activate', methods=['POST'])
def htmx_license_activate():
    """Lizenz aktivieren via HTMX"""
    license_key = request.form.get('license_key', '').strip()

    if not license_key:
        return render_template('partials/toast.html',
            message='Bitte Lizenz-Key eingeben',
            type='error'
        )

    result = activate_license(get_db(), license_key)

    if result['success']:
        return '''
            <div class="toast success">Lizenz erfolgreich aktiviert!</div>
            <script>setTimeout(() => location.reload(), 1500)</script>
        '''
    else:
        return render_template('partials/toast.html',
            message=result['message'],
            type='error'
        )


@app.route('/htmx/logs')
def htmx_logs():
    """Logs-Tabelle"""
    level = request.args.get('level', '')
    limit = int(request.args.get('limit', 50))

    query = 'SELECT * FROM logs WHERE 1=1'
    params = []
    if level:
        query += ' AND level = ?'
        params.append(level)
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)

    logs = get_db().execute(query, params).fetchall()
    return render_template('partials/logs_table.html', logs=logs)

@app.route('/htmx/logs/clear', methods=['DELETE'])
def htmx_clear_logs():
    get_db().execute('DELETE FROM logs')
    get_db().commit()
    return render_template('partials/logs_table.html', logs=[])


@app.route('/htmx/entities')
def htmx_entities():
    """Entities-Übersicht anzeigen"""
    db = get_db()

    # Statistiken
    stats = {
        'members': db.execute('SELECT COUNT(*) as c FROM members').fetchone()['c'],
        'posts': db.execute('SELECT COUNT(*) as c FROM posts').fetchone()['c'],
        'communities': db.execute('SELECT COUNT(*) as c FROM communities').fetchone()['c'],
        'raw_fetches': db.execute('SELECT COUNT(*) as c FROM raw_fetches').fetchone()['c']
    }

    # Sample-Daten (max 20 pro Typ)
    members = db.execute(
        'SELECT * FROM members ORDER BY level DESC, name LIMIT 20'
    ).fetchall()

    posts = db.execute(
        'SELECT * FROM posts ORDER BY likes DESC, created_at DESC LIMIT 20'
    ).fetchall()

    communities = db.execute('SELECT * FROM communities').fetchall()

    return render_template('partials/entities_view.html',
        stats=stats,
        members=members,
        posts=posts,
        communities=communities
    )


@app.route('/htmx/entities/reprocess', methods=['POST'])
def htmx_entities_reprocess():
    """Alle Entities neu extrahieren"""
    count = reprocess_all_raw_fetches()

    # Zeige aktualisierte Ansicht
    db = get_db()
    stats = {
        'members': db.execute('SELECT COUNT(*) as c FROM members').fetchone()['c'],
        'posts': db.execute('SELECT COUNT(*) as c FROM posts').fetchone()['c'],
        'communities': db.execute('SELECT COUNT(*) as c FROM communities').fetchone()['c'],
        'raw_fetches': db.execute('SELECT COUNT(*) as c FROM raw_fetches').fetchone()['c']
    }

    members = db.execute(
        'SELECT * FROM members ORDER BY level DESC, name LIMIT 20'
    ).fetchall()

    posts = db.execute(
        'SELECT * FROM posts ORDER BY likes DESC, created_at DESC LIMIT 20'
    ).fetchall()

    communities = db.execute('SELECT * FROM communities').fetchall()

    return render_template('partials/entities_view.html',
        stats=stats,
        members=members,
        posts=posts,
        communities=communities
    )


@app.route('/htmx/fetches')
def htmx_fetches():
    """Fetches-Tabelle"""
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

    # Entity Types für Filter
    types = get_db().execute('SELECT DISTINCT entity_type FROM raw_fetches').fetchall()

    return render_template('partials/fetches_table.html',
        fetches=fetches,
        entity_types=[t['entity_type'] for t in types],
        current_type=entity_type
    )


# ============================================
# ROUTES - FILTER
# ============================================

@app.route('/htmx/filter/form')
def htmx_filter_form():
    """Dynamisches Filter-Formular nach Typ"""
    output_type = request.args.get('type', 'post')
    communities = get_available_communities()
    return render_template('partials/filter_form.html',
        output_type=output_type,
        communities=communities
    )


@app.route('/htmx/filter/preview', methods=['POST'])
def htmx_filter_preview():
    """Live-Vorschau der Filter-Ergebnisse (nutzt extrahierte Entitäten)"""
    output_type = request.form.get('output_type', 'post')

    # Gemeinsame Filter aus Form extrahieren
    filters = {}
    community_ids = request.form.getlist('community_ids')
    if community_ids:
        filters['community_ids'] = community_ids

    # Text-Suche (für alle Typen)
    search_text = request.form.get('search_text')
    if search_text:
        filters['search_text'] = search_text

    # Sortierung (für alle Typen)
    sort = request.form.get('sort')
    if sort:
        filters['sort'] = sort
    sort_order = request.form.get('sort_order')
    if sort_order:
        filters['sort_order'] = sort_order

    if output_type == 'post':
        # Likes Range
        likes_min = request.form.get('likes_min')
        if likes_min:
            filters['likes_min'] = int(likes_min)
        likes_max = request.form.get('likes_max')
        if likes_max:
            filters['likes_max'] = int(likes_max)

        # Comments Range
        comments_min = request.form.get('comments_min')
        if comments_min:
            filters['comments_min'] = int(comments_min)
        comments_max = request.form.get('comments_max')
        if comments_max:
            filters['comments_max'] = int(comments_max)

        # Datum Range
        date_from = request.form.get('date_from')
        if date_from:
            filters['date_from'] = date_from
        date_to = request.form.get('date_to')
        if date_to:
            filters['date_to'] = date_to

        # Erstellt innerhalb X Tagen
        created_within_days = request.form.get('created_within_days')
        if created_within_days:
            filters['created_within_days'] = int(created_within_days)

        # Nur mit Content
        if request.form.get('has_content'):
            filters['has_content'] = True

        # Nur mit Titel
        if request.form.get('has_title'):
            filters['has_title'] = True

        # Nur mit Medien
        if request.form.get('has_media'):
            filters['has_media'] = True

        # Author-Filter
        author_ids = request.form.getlist('author_ids')
        if author_ids:
            filters['author_ids'] = author_ids

        author_name_contains = request.form.get('author_name_contains')
        if author_name_contains:
            filters['author_name_contains'] = author_name_contains

        exclude_author_ids = request.form.get('exclude_author_ids')
        if exclude_author_ids:
            filters['exclude_author_ids'] = [x.strip() for x in exclude_author_ids.split(',') if x.strip()]

        # Content-Filter
        title_contains = request.form.get('title_contains')
        if title_contains:
            filters['title_contains'] = title_contains

        content_contains = request.form.get('content_contains')
        if content_contains:
            filters['content_contains'] = content_contains

        content_length_min = request.form.get('content_length_min')
        if content_length_min:
            filters['content_length_min'] = int(content_length_min)

        content_length_max = request.form.get('content_length_max')
        if content_length_max:
            filters['content_length_max'] = int(content_length_max)

        results = get_posts(filters)

    elif output_type == 'member':
        # Role-Filter (einzeln oder mehrfach)
        role = request.form.get('role')
        if role:
            filters['role'] = role
        roles = request.form.getlist('roles')
        if roles:
            filters['roles'] = roles

        # Owner-Filter
        if request.form.get('is_owner'):
            filters['is_owner'] = True

        # Level Range
        level_min = request.form.get('level_min')
        if level_min:
            filters['level_min'] = int(level_min)
        level_max = request.form.get('level_max')
        if level_max:
            filters['level_max'] = int(level_max)

        # Post Count Range
        post_count_min = request.form.get('post_count_min')
        if post_count_min:
            filters['post_count_min'] = int(post_count_min)
        post_count_max = request.form.get('post_count_max')
        if post_count_max:
            filters['post_count_max'] = int(post_count_max)

        # Aktivitäts-Filter
        inactive_since_days = request.form.get('inactive_since_days')
        if inactive_since_days:
            filters['inactive_since_days'] = int(inactive_since_days)
        active_in_last_days = request.form.get('active_in_last_days')
        if active_in_last_days:
            filters['active_in_last_days'] = int(active_in_last_days)

        # Joined-Filter
        joined_before_days = request.form.get('joined_before_days')
        if joined_before_days:
            filters['joined_before_days'] = int(joined_before_days)
        joined_within_days = request.form.get('joined_within_days')
        if joined_within_days:
            filters['joined_within_days'] = int(joined_within_days)
        joined_after = request.form.get('joined_after')
        if joined_after:
            filters['joined_after'] = joined_after
        joined_before = request.form.get('joined_before')
        if joined_before:
            filters['joined_before'] = joined_before

        # Profilbild-Filter
        if request.form.get('has_picture'):
            filters['has_picture'] = True

        # Bio-Suche
        bio_contains = request.form.get('bio_contains')
        if bio_contains:
            filters['bio_contains'] = bio_contains

        # Exclude Member IDs
        exclude_member_ids = request.form.get('exclude_member_ids')
        if exclude_member_ids:
            filters['exclude_member_ids'] = [x.strip() for x in exclude_member_ids.split(',') if x.strip()]

        results = get_members(filters)

    elif output_type == 'community':
        # Member Count Range
        member_count_min = request.form.get('member_count_min')
        if member_count_min:
            filters['member_count_min'] = int(member_count_min)
        member_count_max = request.form.get('member_count_max')
        if member_count_max:
            filters['member_count_max'] = int(member_count_max)

        # Post Count Range
        post_count_min = request.form.get('post_count_min')
        if post_count_min:
            filters['post_count_min'] = int(post_count_min)
        post_count_max = request.form.get('post_count_max')
        if post_count_max:
            filters['post_count_max'] = int(post_count_max)

        # Nur mit Logo/Bild
        if request.form.get('has_picture'):
            filters['has_picture'] = True

        # Shared Members Filter (für Community-Vergleich)
        min_shared = request.form.get('min_shared_members')
        if min_shared:
            filters['min_shared_members'] = int(min_shared)
            results = get_communities_with_shared_members(filters)
        else:
            results = get_communities(filters)

    else:
        results = []

    # Temporäres Selection-Objekt für Template
    selection = {
        'name': 'Vorschau',
        'output_type': output_type
    }

    return render_template('partials/selection_results.html',
        selection=selection,
        results=results[:100],
        total=len(results)
    )


@app.route('/htmx/filter/save', methods=['POST'])
def htmx_filter_save():
    """Filter als Selektion speichern - speichert alle konfigurierten Filter"""
    name = request.form.get('selection_name')
    if not name:
        return render_template('partials/toast.html', message='Name erforderlich!', type='error')

    output_type = request.form.get('output_type', 'post')

    # Alle Filter aus Form extrahieren (gleiche Logik wie in htmx_filter_preview)
    filters = {}

    # Gemeinsame Filter
    community_ids = request.form.getlist('community_ids')
    if community_ids:
        filters['community_ids'] = community_ids

    search_text = request.form.get('search_text')
    if search_text:
        filters['search_text'] = search_text

    sort = request.form.get('sort')
    if sort:
        filters['sort'] = sort
    sort_order = request.form.get('sort_order')
    if sort_order:
        filters['sort_order'] = sort_order

    if output_type == 'post':
        # Alle Post-Filter
        for field in ['likes_min', 'likes_max', 'comments_min', 'comments_max',
                      'created_within_days', 'content_length_min', 'content_length_max']:
            val = request.form.get(field)
            if val:
                filters[field] = int(val)

        for field in ['date_from', 'date_to', 'author_name_contains',
                      'title_contains', 'content_contains']:
            val = request.form.get(field)
            if val:
                filters[field] = val

        for field in ['has_content', 'has_title', 'has_media']:
            if request.form.get(field):
                filters[field] = True

        exclude_author_ids = request.form.get('exclude_author_ids')
        if exclude_author_ids:
            filters['exclude_author_ids'] = [x.strip() for x in exclude_author_ids.split(',') if x.strip()]

    elif output_type == 'member':
        # Alle Member-Filter
        roles = request.form.getlist('roles')
        if roles:
            filters['roles'] = roles
        role = request.form.get('role')
        if role:
            filters['role'] = role

        for field in ['level_min', 'level_max', 'post_count_min', 'post_count_max',
                      'active_in_last_days', 'inactive_since_days',
                      'joined_within_days', 'joined_before_days']:
            val = request.form.get(field)
            if val:
                filters[field] = int(val)

        for field in ['joined_after', 'joined_before', 'bio_contains']:
            val = request.form.get(field)
            if val:
                filters[field] = val

        for field in ['is_owner', 'has_picture']:
            if request.form.get(field):
                filters[field] = True

        exclude_member_ids = request.form.get('exclude_member_ids')
        if exclude_member_ids:
            filters['exclude_member_ids'] = [x.strip() for x in exclude_member_ids.split(',') if x.strip()]

    elif output_type == 'community':
        # Alle Community-Filter
        for field in ['member_count_min', 'member_count_max', 'post_count_min',
                      'post_count_max', 'min_shared_members']:
            val = request.form.get(field)
            if val:
                filters[field] = int(val)

        if request.form.get('has_picture'):
            filters['has_picture'] = True

    db = get_db()
    db.execute('''
        INSERT INTO selections (name, output_type, filters_json, created_by)
        VALUES (?, ?, ?, ?)
    ''', (name, output_type, json.dumps(filters), 'user'))
    db.commit()

    return render_template('partials/toast.html', message=f'Selektion "{name}" gespeichert!', type='success')


# ============================================
# ROUTES - CHAT
# ============================================

@app.route('/htmx/chats')
def htmx_chat_sidebar():
    """Chat-Sidebar"""
    chats = get_db().execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    active_chat = request.args.get('active', type=int)
    return render_template('partials/chat_sidebar.html', chats=chats, active_chat=active_chat)

@app.route('/htmx/chat/<int:chat_id>')
def htmx_chat_messages(chat_id):
    """Chat-Nachrichten laden"""
    db = get_db()
    messages = db.execute(
        'SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at',
        (chat_id,)
    ).fetchall()

    # Lade alle Selektionen, die mit Nachrichten in diesem Chat verknüpft sind
    message_ids = [m['id'] for m in messages]
    selections_by_message = {}
    if message_ids:
        placeholders = ','.join(['?' for _ in message_ids])
        selections = db.execute(f'''
            SELECT * FROM selections
            WHERE message_id IN ({placeholders})
            ORDER BY created_at
        ''', message_ids).fetchall()
        for sel in selections:
            mid = sel['message_id']
            if mid not in selections_by_message:
                selections_by_message[mid] = []
            selections_by_message[mid].append(sel)

    return render_template('partials/chat_messages.html',
                          messages=messages,
                          chat_id=chat_id,
                          selections_by_message=selections_by_message)

@app.route('/htmx/chat', methods=['POST'])
def htmx_create_chat():
    """Neuen Chat erstellen"""
    db = get_db()
    cursor = db.execute('INSERT INTO chats (title) VALUES (?)', ('Neuer Chat',))
    db.commit()
    chat_id = cursor.lastrowid

    # Sidebar und Chat-Bereich neu rendern
    chats = db.execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()

    response = render_template('partials/chat_sidebar.html', chats=chats, active_chat=chat_id)
    response += f'''
    <div id="chat-main" hx-swap-oob="innerHTML">
        {render_template('partials/chat_messages.html', messages=[], chat_id=chat_id)}
    </div>
    '''
    return response

@app.route('/htmx/chat/<int:chat_id>/delete', methods=['DELETE'])
def htmx_delete_chat(chat_id):
    """Chat löschen"""
    db = get_db()
    db.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    db.commit()

    chats = db.execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    return render_template('partials/chat_sidebar.html', chats=chats)

@app.route('/htmx/chat/<int:chat_id>/message', methods=['POST'])
def htmx_send_message(chat_id):
    """Nachricht senden und AI-Antwort generieren"""
    content = request.form.get('content', '').strip()
    if not content:
        return '', 204

    db = get_db()

    # User-Nachricht speichern
    db.execute(
        'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
        (chat_id, 'user', content)
    )
    db.commit()

    # AI-Antwort generieren
    api_key = get_setting('openai_api_key')
    if not api_key:
        db.execute(
            'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
            (chat_id, 'assistant', 'Bitte OpenAI API Key in Settings konfigurieren.')
        )
        db.commit()
        return htmx_chat_messages(chat_id)

    # Kontext laden
    messages = db.execute(
        'SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at',
        (chat_id,)
    ).fetchall()

    # OpenAI Call
    response = call_openai(api_key, [{'role': m['role'], 'content': m['content']} for m in messages])

    # Selektionen aus der Antwort extrahieren
    clean_response, selections = extract_selections_from_response(response)

    # Assistant-Nachricht speichern (mit bereinigtem Text)
    cursor = db.execute(
        'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
        (chat_id, 'assistant', clean_response)
    )
    message_id = cursor.lastrowid

    # Selektionen erstellen und mit der Nachricht verknüpfen
    for sel in selections:
        db.execute('''
            INSERT INTO selections (name, output_type, filters_json, created_by, message_id)
            VALUES (?, ?, ?, 'assistant', ?)
        ''', (
            sel.get('name', 'AI-Selektion'),
            sel.get('output_type', 'post'),
            json.dumps(sel.get('filters', {})),
            message_id
        ))

    db.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (datetime.now(), chat_id))
    db.commit()

    return htmx_chat_messages(chat_id)

# ============================================
# OPENAI INTEGRATION
# ============================================

def extract_selections_from_response(response_text):
    """
    Extrahiert Selektionen aus der AI-Antwort.
    Format: [[SELECTION:{"name": "...", "output_type": "...", "filters": {...}}]]

    Returns:
        tuple: (clean_text, list of selection dicts)
    """
    pattern = r'\[\[SELECTION:(.*?)\]\]'
    selections = []

    for match in re.finditer(pattern, response_text):
        try:
            selection_data = json.loads(match.group(1))
            if 'name' in selection_data and 'output_type' in selection_data:
                selections.append(selection_data)
        except json.JSONDecodeError:
            continue

    # Entferne die Selection-Tags aus dem Text für die Anzeige
    clean_text = re.sub(pattern, '', response_text).strip()

    return clean_text, selections


def call_openai(api_key, messages, model='gpt-4o-mini'):
    """Einfacher OpenAI API Call"""
    system_prompt = """Du bist ein hilfreicher Assistent für die Analyse von Skool-Community-Daten.
Du hilfst beim Erstellen von Selektionen, Filtern und Berichten.

WICHTIG: Du kannst Selektionen (Filter) erstellen! Wenn der User nach einem Filter oder einer Selektion fragt,
erstelle eine mit folgendem Format (das JSON muss in einer einzelnen Zeile sein):

[[SELECTION:{"name": "Name der Selektion", "output_type": "post|member|community", "filters": {...}}]]

Verfügbare output_types und ihre Filter:

1. output_type: "post" - Filtert Posts
   Filter: community_ids (list), author_ids (list), likes_min (int), likes_max (int),
   comments_min (int), comments_max (int), date_from (YYYY-MM-DD), date_to (YYYY-MM-DD),
   created_within_days (int), search_text (str), has_content (bool), has_title (bool),
   title_contains (str), content_contains (str), sort (likes|comments|created_at|title), sort_order (ASC|DESC)

2. output_type: "member" - Filtert Mitglieder
   Filter: community_ids (list), roles (list: admin/group-moderator/member/owner), is_owner (bool),
   level_min (int), level_max (int), post_count_min (int), post_count_max (int),
   active_in_last_days (int), inactive_since_days (int), joined_within_days (int),
   bio_contains (str), has_picture (bool), sort (name|level|post_count|joined_at|last_online), sort_order (ASC|DESC)

3. output_type: "community" - Für Community-Vergleiche
   Filter: community_ids (list), member_count_min (int), member_count_max (int),
   post_count_min (int), post_count_max (int), min_shared_members (int)

Beispiel: User fragt "Zeige mir Posts mit mehr als 50 Likes"
Antwort: Hier ist eine Selektion für Posts mit mehr als 50 Likes:
[[SELECTION:{"name": "Posts mit 50+ Likes", "output_type": "post", "filters": {"likes_min": 50, "sort": "likes", "sort_order": "DESC"}}]]

Schreibe IMMER einen kurzen erklärenden Text VOR der Selektion."""

    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system_prompt}] + messages,
        'max_tokens': 2000
    }

    req = Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    try:
        with urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
            data = json.loads(response.read())
            return data['choices'][0]['message']['content']
    except Exception as e:
        return f'Fehler bei OpenAI-Anfrage: {str(e)}'

# ============================================
# DATA ACCESS (aus extrahierten Entitäten)
# ============================================

def get_latest_fetches_by_type(entity_type):
    """Holt neueste Fetches pro Entity-ID (für Legacy-Kompatibilität)"""
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


def get_posts(filters: dict = None) -> list[dict]:
    """
    Holt Posts aus der posts-Tabelle (extrahierte Entitäten).

    Args:
        filters: Optional dict mit Filtern:
            - community_ids: list[str] - Filter nach Community-IDs
            - author_ids: list[str] - Filter nach Author-IDs
            - likes_min: int - Minimum Likes
            - likes_max: int - Maximum Likes
            - comments_min: int - Minimum Comments
            - comments_max: int - Maximum Comments
            - date_from: str - Datum ab (YYYY-MM-DD oder ISO)
            - date_to: str - Datum bis (YYYY-MM-DD oder ISO)
            - created_within_days: int - Erstellt innerhalb X Tagen
            - search_text: str - Suche in Title/Content
            - has_content: bool - Nur Posts mit Content
            - sort: str - Sortierung (likes, comments, created_at, title)
            - sort_order: str - ASC oder DESC (default: DESC)
            - limit: int - Maximale Anzahl Ergebnisse

    Returns:
        Liste von Post-Dictionaries
    """
    filters = filters or {}
    db = get_db()

    query = 'SELECT * FROM posts WHERE 1=1'
    params = []

    # Community-Filter
    if filters.get('community_ids'):
        placeholders = ','.join(['?' for _ in filters['community_ids']])
        query += f' AND community_id IN ({placeholders})'
        params.extend(filters['community_ids'])

    # Author-Filter
    if filters.get('author_ids'):
        placeholders = ','.join(['?' for _ in filters['author_ids']])
        query += f' AND author_id IN ({placeholders})'
        params.extend(filters['author_ids'])

    # Likes Range
    if filters.get('likes_min') is not None:
        query += ' AND likes >= ?'
        params.append(int(filters['likes_min']))

    if filters.get('likes_max') is not None:
        query += ' AND likes <= ?'
        params.append(int(filters['likes_max']))

    # Comments Range
    if filters.get('comments_min') is not None:
        query += ' AND comments >= ?'
        params.append(int(filters['comments_min']))

    if filters.get('comments_max') is not None:
        query += ' AND comments <= ?'
        params.append(int(filters['comments_max']))

    # Datum Range
    if filters.get('date_from'):
        query += ' AND created_at >= ?'
        params.append(filters['date_from'])

    if filters.get('date_to'):
        query += ' AND created_at <= ?'
        params.append(filters['date_to'])

    # Erstellt innerhalb X Tagen
    if filters.get('created_within_days'):
        days = int(filters['created_within_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND created_at >= ?'
        params.append(cutoff)

    # Nur mit Content
    if filters.get('has_content'):
        query += " AND content IS NOT NULL AND content != ''"

    # Nur mit Titel
    if filters.get('has_title'):
        query += " AND title IS NOT NULL AND title != ''"

    # Nur mit Medien (media_urls ist JSON Array)
    if filters.get('has_media'):
        query += " AND media_urls IS NOT NULL AND media_urls != '[]' AND media_urls != ''"

    # Content Length Filter
    if filters.get('content_length_min') is not None:
        query += ' AND LENGTH(COALESCE(content, "")) >= ?'
        params.append(int(filters['content_length_min']))

    if filters.get('content_length_max') is not None:
        query += ' AND LENGTH(COALESCE(content, "")) <= ?'
        params.append(int(filters['content_length_max']))

    # Exclude Author IDs
    if filters.get('exclude_author_ids'):
        placeholders = ','.join(['?' for _ in filters['exclude_author_ids']])
        query += f' AND author_id NOT IN ({placeholders})'
        params.extend(filters['exclude_author_ids'])

    # Sortierung
    sort_field = filters.get('sort', 'likes')
    sort_order = filters.get('sort_order', 'DESC').upper()
    if sort_order not in ('ASC', 'DESC'):
        sort_order = 'DESC'

    valid_sorts = {
        'likes': 'likes',
        'comments': 'comments',
        'created_at': 'created_at',
        'title': 'title'
    }
    sort_column = valid_sorts.get(sort_field, 'likes')
    query += f' ORDER BY {sort_column} {sort_order}'

    # Sekundäre Sortierung
    if sort_column != 'created_at':
        query += ', created_at DESC'

    # Limit
    if filters.get('limit'):
        query += ' LIMIT ?'
        params.append(int(filters['limit']))

    rows = db.execute(query, params).fetchall()
    posts = [dict(row) for row in rows]

    # Text-Suche in Python (SQLite LIKE ist case-sensitive)
    if filters.get('search_text'):
        search = filters['search_text'].lower()
        posts = [p for p in posts if search in (p.get('title') or '').lower()
                 or search in (p.get('content') or '').lower()]

    # Title Contains (separat)
    if filters.get('title_contains'):
        search = filters['title_contains'].lower()
        posts = [p for p in posts if search in (p.get('title') or '').lower()]

    # Content Contains (separat)
    if filters.get('content_contains'):
        search = filters['content_contains'].lower()
        posts = [p for p in posts if search in (p.get('content') or '').lower()]

    # Author Name Contains
    if filters.get('author_name_contains'):
        search = filters['author_name_contains'].lower()
        posts = [p for p in posts if search in (p.get('author_name') or '').lower()]

    return posts


def get_members(filters: dict = None) -> list[dict]:
    """
    Holt Members aus der members-Tabelle (extrahierte Entitäten).

    Args:
        filters: Optional dict mit Filtern:
            - community_ids: list[str] - Filter nach Community-IDs
            - role: str - Einzelne Rolle (legacy)
            - roles: list[str] - Filter nach Rollen (admin, group-moderator, member, owner)
            - is_owner: bool - Nur Owner
            - level_min: int - Minimum Level
            - level_max: int - Maximum Level
            - post_count_min: int - Minimum Post-Anzahl
            - post_count_max: int - Maximum Post-Anzahl
            - search_text: str - Suche in Name/Slug
            - inactive_since_days: int - Inaktiv seit X Tagen (last_online < cutoff)
            - active_in_last_days: int - Aktiv in letzten X Tagen (last_online > cutoff)
            - joined_before_days: int - Beigetreten vor X Tagen
            - joined_within_days: int - Beigetreten innerhalb X Tagen
            - joined_after: str - Beigetreten nach Datum (YYYY-MM-DD)
            - joined_before: str - Beigetreten vor Datum (YYYY-MM-DD)
            - has_picture: bool - Nur Members mit Profilbild
            - sort: str - Sortierung (name, level, post_count, joined, last_online)
            - sort_order: str - ASC oder DESC (default: DESC)
            - limit: int - Maximale Anzahl Ergebnisse

    Returns:
        Liste von Member-Dictionaries
    """
    filters = filters or {}
    db = get_db()

    query = 'SELECT * FROM members WHERE 1=1'
    params = []

    # Community-Filter
    if filters.get('community_ids'):
        placeholders = ','.join(['?' for _ in filters['community_ids']])
        query += f' AND community_id IN ({placeholders})'
        params.extend(filters['community_ids'])

    # Role-Filter (legacy: einzelne role)
    if filters.get('role'):
        query += ' AND role = ?'
        params.append(filters['role'])

    # Role-Filter (neu: mehrere roles)
    if filters.get('roles'):
        placeholders = ','.join(['?' for _ in filters['roles']])
        query += f' AND role IN ({placeholders})'
        params.extend(filters['roles'])

    # Owner-Filter
    if filters.get('is_owner'):
        query += ' AND is_owner = 1'

    # Level Range
    if filters.get('level_min') is not None:
        query += ' AND level >= ?'
        params.append(int(filters['level_min']))

    if filters.get('level_max') is not None:
        query += ' AND level <= ?'
        params.append(int(filters['level_max']))

    # Post Count Range
    if filters.get('post_count_min') is not None:
        query += ' AND post_count >= ?'
        params.append(int(filters['post_count_min']))

    if filters.get('post_count_max') is not None:
        query += ' AND post_count <= ?'
        params.append(int(filters['post_count_max']))

    # Profilbild-Filter
    if filters.get('has_picture'):
        query += " AND picture IS NOT NULL AND picture != ''"

    # Exclude Member IDs
    if filters.get('exclude_member_ids'):
        placeholders = ','.join(['?' for _ in filters['exclude_member_ids']])
        query += f' AND id NOT IN ({placeholders})'
        params.extend(filters['exclude_member_ids'])

    # Aktivitäts-Filter (basierend auf last_online)
    # Inaktiv seit X Tagen: zeige Members deren last_online VOR dem Cutoff liegt
    if filters.get('inactive_since_days'):
        days = int(filters['inactive_since_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND (last_online IS NULL OR last_online < ?)'
        params.append(cutoff)

    # Aktiv in letzten X Tagen: zeige Members deren last_online NACH dem Cutoff liegt
    if filters.get('active_in_last_days'):
        days = int(filters['active_in_last_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND last_online >= ?'
        params.append(cutoff)

    # Joined-Filter (basierend auf joined_at)
    # Beigetreten vor X Tagen: ältere Members
    if filters.get('joined_before_days'):
        days = int(filters['joined_before_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND joined_at < ?'
        params.append(cutoff)

    # Beigetreten innerhalb X Tagen: neue Members
    if filters.get('joined_within_days'):
        days = int(filters['joined_within_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND joined_at >= ?'
        params.append(cutoff)

    # Exakte Datum-Filter
    if filters.get('joined_after'):
        query += ' AND joined_at >= ?'
        params.append(filters['joined_after'])

    if filters.get('joined_before'):
        query += ' AND joined_at <= ?'
        params.append(filters['joined_before'])

    # Sortierung
    sort_field = filters.get('sort', 'level')
    sort_order = filters.get('sort_order', 'DESC').upper()
    if sort_order not in ('ASC', 'DESC'):
        sort_order = 'DESC'

    valid_sorts = {
        'name': 'name',
        'level': 'level',
        'post_count': 'post_count',
        'joined': 'joined_at',
        'joined_at': 'joined_at',
        'last_online': 'last_online',
        'last_active': 'last_online'  # Alias
    }
    sort_column = valid_sorts.get(sort_field, 'level')
    query += f' ORDER BY {sort_column} {sort_order}'

    # Sekundäre Sortierung
    if sort_column != 'name':
        query += ', name ASC'

    # Limit
    if filters.get('limit'):
        query += ' LIMIT ?'
        params.append(int(filters['limit']))

    rows = db.execute(query, params).fetchall()
    members = [dict(row) for row in rows]

    # Text-Suche in Python (case-insensitive)
    if filters.get('search_text'):
        search = filters['search_text'].lower()
        members = [m for m in members if search in (m.get('name') or '').lower()
                   or search in (m.get('slug') or '').lower()]

    # Bio Contains (separat)
    if filters.get('bio_contains'):
        search = filters['bio_contains'].lower()
        members = [m for m in members if search in (m.get('bio') or '').lower()]

    return members


def get_communities(filters: dict = None) -> list[dict]:
    """
    Holt Communities aus der communities-Tabelle (extrahierte Entitäten).

    Args:
        filters: Optional dict mit Filtern:
            - ids: list[str] - Filter nach Community-IDs
            - slugs: list[str] - Filter nach Slugs
            - search_text: str - Suche in Name/Description
            - member_count_min: int - Minimum Member-Anzahl
            - member_count_max: int - Maximum Member-Anzahl
            - post_count_min: int - Minimum Post-Anzahl
            - post_count_max: int - Maximum Post-Anzahl
            - sort: str - Sortierung (name, member_count, post_count)
            - sort_order: str - ASC oder DESC (default: DESC)
            - limit: int - Maximale Anzahl Ergebnisse

    Returns:
        Liste von Community-Dictionaries
    """
    filters = filters or {}
    db = get_db()

    query = 'SELECT * FROM communities WHERE 1=1'
    params = []

    # ID-Filter
    if filters.get('ids'):
        placeholders = ','.join(['?' for _ in filters['ids']])
        query += f' AND id IN ({placeholders})'
        params.extend(filters['ids'])

    # Slug-Filter
    if filters.get('slugs'):
        placeholders = ','.join(['?' for _ in filters['slugs']])
        query += f' AND slug IN ({placeholders})'
        params.extend(filters['slugs'])

    # Member Count Range
    if filters.get('member_count_min') is not None:
        query += ' AND member_count >= ?'
        params.append(int(filters['member_count_min']))

    if filters.get('member_count_max') is not None:
        query += ' AND member_count <= ?'
        params.append(int(filters['member_count_max']))

    # Post Count Range
    if filters.get('post_count_min') is not None:
        query += ' AND post_count >= ?'
        params.append(int(filters['post_count_min']))

    if filters.get('post_count_max') is not None:
        query += ' AND post_count <= ?'
        params.append(int(filters['post_count_max']))

    # Hat Logo/Bild Filter
    if filters.get('has_picture'):
        query += " AND picture IS NOT NULL AND picture != ''"

    # Sortierung
    sort_field = filters.get('sort', 'member_count')
    sort_order = filters.get('sort_order', 'DESC').upper()
    if sort_order not in ('ASC', 'DESC'):
        sort_order = 'DESC'

    valid_sorts = {
        'name': 'name',
        'member_count': 'member_count',
        'post_count': 'post_count'
    }
    sort_column = valid_sorts.get(sort_field, 'member_count')
    query += f' ORDER BY {sort_column} {sort_order}'

    # Limit
    if filters.get('limit'):
        query += ' LIMIT ?'
        params.append(int(filters['limit']))

    rows = db.execute(query, params).fetchall()
    communities = [dict(row) for row in rows]

    # Text-Suche in Python (case-insensitive)
    if filters.get('search_text'):
        search = filters['search_text'].lower()
        communities = [c for c in communities if search in (c.get('name') or '').lower()
                       or search in (c.get('description') or '').lower()
                       or search in (c.get('slug') or '').lower()]

    return communities


# Legacy-Funktionen für Abwärtskompatibilität (deprecated)
def extract_posts():
    """DEPRECATED: Nutze get_posts() stattdessen"""
    return get_posts()


def extract_members():
    """DEPRECATED: Nutze get_members() stattdessen"""
    return get_members()

# ============================================
# SELECTIONS
# ============================================

@app.route('/htmx/selections')
def htmx_selections():
    """Alle Selections anzeigen"""
    selections = get_db().execute('SELECT * FROM selections ORDER BY created_at DESC').fetchall()
    return render_template('partials/selections_list.html', selections=selections)

@app.route('/htmx/selection/<int:selection_id>/execute')
def htmx_execute_selection(selection_id):
    """Selection ausführen und Ergebnisse anzeigen (nutzt extrahierte Entitäten)"""
    selection = get_db().execute('SELECT * FROM selections WHERE id = ?', (selection_id,)).fetchone()
    if not selection:
        return 'Selection nicht gefunden', 404

    filters = json.loads(selection['filters_json'])
    output_type = selection['output_type']

    # Daten aus extrahierten Entitäten holen (mit DB-Level Filterung)
    if output_type == 'post':
        results = get_posts(filters)
    elif output_type == 'member':
        results = get_members(filters)
    elif output_type == 'community':
        results = get_communities_with_shared_members(filters)
    else:
        results = []

    # Result Count updaten
    get_db().execute(
        'UPDATE selections SET result_count = ? WHERE id = ?',
        (len(results), selection_id)
    )
    get_db().commit()

    return render_template('partials/selection_results.html',
        selection=selection,
        results=results[:100],  # Max 100 anzeigen
        total=len(results)
    )

# ============================================
# PROMPT TEMPLATES
# ============================================

DEFAULT_TEMPLATES = [
    {
        "name": "Community Analyse",
        "category": "analysis",
        "content": "Analysiere die Community '{community_name}' basierend auf den folgenden Daten:\n\n{data}\n\nBitte identifiziere:\n1. Hauptthemen und Trends\n2. Aktivste Member\n3. Engagement-Muster\n4. Verbesserungsvorschläge",
        "description": "Grundlegende Community-Analyse"
    },
    {
        "name": "Member Engagement",
        "category": "analysis",
        "content": "Bewerte das Engagement der folgenden Members basierend auf Posts, Likes und Kommentaren:\n\n{data}\n\nBitte kategorisiere die Members nach:\n1. Sehr aktiv (Top 10%)\n2. Aktiv\n3. Gelegentlich aktiv\n4. Inaktiv",
        "description": "Member-Aktivitäts-Analyse"
    },
    {
        "name": "Content Summary",
        "category": "summary",
        "content": "Fasse die wichtigsten Posts und Diskussionen zusammen:\n\n{data}\n\nStrukturiere die Zusammenfassung nach:\n1. Hauptthemen\n2. Wichtigste Erkenntnisse\n3. Offene Fragen/Diskussionen",
        "description": "Content-Zusammenfassung"
    },
    {
        "name": "Trend Analyse",
        "category": "analysis",
        "content": "Analysiere die Trends in der Community über Zeit:\n\n{data}\n\nIdentifiziere:\n1. Wachsende Themen\n2. Abnehmende Themen\n3. Saisonale Muster\n4. Engagement-Trends",
        "description": "Zeitliche Trend-Analyse"
    }
]


def init_default_templates():
    """Initialisiert Standard-Prompt-Templates wenn keine vorhanden"""
    db = get_db()
    count = db.execute('SELECT COUNT(*) as c FROM prompt_templates').fetchone()['c']
    if count == 0:
        for tpl in DEFAULT_TEMPLATES:
            db.execute(
                'INSERT INTO prompt_templates (name, content, description, category) VALUES (?, ?, ?, ?)',
                (tpl['name'], tpl['content'], tpl['description'], tpl['category'])
            )
        db.commit()


@app.route('/api/prompt-templates', methods=['GET', 'POST'])
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


@app.route('/api/prompt-template', methods=['GET', 'PUT', 'DELETE'])
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
# SELECTIONS API (erweitert)
# ============================================

@app.route('/api/selections', methods=['GET', 'POST'])
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


@app.route('/api/selection', methods=['GET', 'PUT', 'DELETE'])
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


@app.route('/api/selection/execute', methods=['GET'])
def api_execute_selection():
    """Selection ausführen (nutzt extrahierte Entitäten)"""
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

    # Daten aus extrahierten Entitäten holen (mit DB-Level Filterung)
    if output_type == 'post':
        results = get_posts(filters)

    elif output_type == 'member':
        results = get_members(filters)

    elif output_type == 'community':
        results = get_communities_with_shared_members(filters)
    else:
        results = []

    # Result Count und IDs cachen
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


@app.route('/api/selection/duplicate', methods=['POST'])
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


def get_communities_with_shared_members(filters: dict) -> list:
    """
    Ermittelt Communities mit gemeinsamen Members (nutzt extrahierte Entitäten).

    Args:
        filters: dict mit:
            - community_ids: list[str] - Die zu vergleichenden Communities
            - min_shared_members: int - Minimum Anzahl gemeinsamer Members

    Returns:
        Liste von Community-Paaren mit shared_members Count
    """
    community_ids = filters.get('community_ids', [])
    min_shared = filters.get('min_shared_members', 1)

    if len(community_ids) < 2:
        return []

    # Nutze get_members() (liest aus members-Tabelle)
    members = get_members()

    # Gruppiere Members nach User-ID
    user_communities = {}
    for m in members:
        uid = m['id']
        cid = m['community_id']
        if uid not in user_communities:
            user_communities[uid] = set()
        user_communities[uid].add(cid)

    # Zähle Shared Members zwischen Community-Paaren
    from itertools import combinations
    results = []
    for c1, c2 in combinations(community_ids, 2):
        shared_count = sum(
            1 for comms in user_communities.values()
            if c1 in comms and c2 in comms
        )
        if shared_count >= min_shared:
            results.append({
                'id': f"{c1}_{c2}",
                'community_1': c1,
                'community_2': c2,
                'shared_members': shared_count
            })

    return results


# Legacy-Alias für Abwärtskompatibilität (deprecated)
def extract_communities_with_shared_members(filters: dict) -> list:
    """DEPRECATED: Nutze get_communities_with_shared_members() stattdessen"""
    return get_communities_with_shared_members(filters)


# ============================================
# SCHEMA INTROSPECTION
# ============================================

@app.route('/api/schema', methods=['GET'])
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


@app.route('/api/table-data', methods=['GET'])
def api_table_data():
    """Query beliebige Tabelle mit Filtern"""
    table = request.args.get('table')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    # SQL Injection verhindern
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
# ACTIVITY TIMELINE
# ============================================

@app.route('/api/activity', methods=['GET'])
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

    # Gruppiere nach Tag
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


@app.route('/api/connections', methods=['GET'])
def api_connections():
    """Netzwerk der Member-Interaktionen (nutzt extrahierte Entitäten)"""
    community_id = request.args.get('community_id', '')

    # Filter für Community vorbereiten
    filters = {}
    if community_id:
        filters['community_ids'] = [community_id]

    # Nutze get_members() und get_posts() mit Filtern
    members = get_members(filters)
    posts = get_posts(filters)

    # Build nodes from members
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

    # Build edges from post interactions (simplified - just based on post count)
    edges = []
    author_posts = {}
    for p in posts:
        aid = p.get('author_id')
        if aid:
            if aid not in author_posts:
                author_posts[aid] = 0
            author_posts[aid] += 1

    # Create edges between active posters (simplified network)
    active_authors = [aid for aid, count in author_posts.items() if count >= 2]
    for i, a1 in enumerate(active_authors):
        for a2 in active_authors[i+1:]:
            edges.append({
                'from': a1,
                'to': a2,
                'weight': min(author_posts.get(a1, 0), author_posts.get(a2, 0))
            })

    return {
        'nodes': nodes[:100],  # Limit for performance
        'edges': edges[:200],
        'total_nodes': len(nodes),
        'total_edges': len(edges)
    }


# ============================================
# MAIN
# ============================================

def open_browser(port):
    webbrowser.open(f'http://localhost:{port}')

def main():
    import argparse
    parser = argparse.ArgumentParser(description='CatKnows Local Server')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Server port')
    parser.add_argument('--no-browser', action='store_true', help='Dont open browser')
    args = parser.parse_args()

    init_db()

    # Default Prompt Templates initialisieren
    with app.app_context():
        init_default_templates()

    # Lizenz pruefen beim Start
    with app.app_context():
        license_status = check_license(get_db())
        if not license_status['has_license']:
            print('[License] Keine Lizenz aktiviert. Bitte im Browser aktivieren.')
        elif not license_status['is_valid']:
            print(f'[License] {license_status["message"]}')
        elif license_status['in_grace_period']:
            print(f'[License] WARNUNG: {license_status["message"]}')
        elif license_status['server_status'] == 'offline':
            print('[License] Server nicht erreichbar - Offline-Modus aktiv')
        else:
            print(f'[License] Gueltig bis {license_status["valid_until"]}')

    print(f'Starting CatKnows on http://localhost:{args.port}')
    print(f'Data directory: {DATA_DIR}')

    if not args.no_browser:
        Timer(0.5, open_browser, [args.port]).start()

    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)

if __name__ == '__main__':
    main()

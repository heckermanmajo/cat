"""
Data Access - Daten-Abfragen, Filter und Templates
"""

from datetime import datetime, timedelta
from itertools import combinations

from db import get_db


# ============================================
# FILTER EXTRACTION (dedupliziert)
# ============================================

def extract_filters_from_form(form, output_type: str) -> dict:
    """
    Extrahiert Filter aus einem Request-Formular.
    Wird von htmx_filter_preview und htmx_filter_save genutzt.
    """
    filters = {}

    # Gemeinsame Filter
    community_ids = form.getlist('community_ids')
    if community_ids:
        filters['community_ids'] = community_ids

    search_text = form.get('search_text')
    if search_text:
        filters['search_text'] = search_text

    sort = form.get('sort')
    if sort:
        filters['sort'] = sort

    sort_order = form.get('sort_order')
    if sort_order:
        filters['sort_order'] = sort_order

    if output_type == 'post':
        # Integer-Felder
        for field in ['likes_min', 'likes_max', 'comments_min', 'comments_max',
                      'created_within_days', 'content_length_min', 'content_length_max']:
            val = form.get(field)
            if val:
                filters[field] = int(val)

        # String-Felder
        for field in ['date_from', 'date_to', 'author_name_contains',
                      'title_contains', 'content_contains']:
            val = form.get(field)
            if val:
                filters[field] = val

        # Boolean-Felder
        for field in ['has_content', 'has_title', 'has_media']:
            if form.get(field):
                filters[field] = True

        # Listen-Felder
        author_ids = form.getlist('author_ids')
        if author_ids:
            filters['author_ids'] = author_ids

        exclude_author_ids = form.get('exclude_author_ids')
        if exclude_author_ids:
            filters['exclude_author_ids'] = [x.strip() for x in exclude_author_ids.split(',') if x.strip()]

    elif output_type == 'member':
        # Rollen
        roles = form.getlist('roles')
        if roles:
            filters['roles'] = roles
        role = form.get('role')
        if role:
            filters['role'] = role

        # Integer-Felder
        for field in ['level_min', 'level_max', 'post_count_min', 'post_count_max',
                      'active_in_last_days', 'inactive_since_days',
                      'joined_within_days', 'joined_before_days']:
            val = form.get(field)
            if val:
                filters[field] = int(val)

        # String-Felder
        for field in ['joined_after', 'joined_before', 'bio_contains']:
            val = form.get(field)
            if val:
                filters[field] = val

        # Boolean-Felder
        for field in ['is_owner', 'has_picture']:
            if form.get(field):
                filters[field] = True

        # Listen-Felder
        exclude_member_ids = form.get('exclude_member_ids')
        if exclude_member_ids:
            filters['exclude_member_ids'] = [x.strip() for x in exclude_member_ids.split(',') if x.strip()]

    elif output_type == 'community':
        # Integer-Felder
        for field in ['member_count_min', 'member_count_max', 'post_count_min',
                      'post_count_max', 'min_shared_members']:
            val = form.get(field)
            if val:
                filters[field] = int(val)

        if form.get('has_picture'):
            filters['has_picture'] = True

    return filters


# ============================================
# COMMUNITIES
# ============================================

def get_available_communities() -> list[dict]:
    """Holt alle Communities aus der communities-Tabelle mit ID und Name"""
    rows = get_db().execute('''
        SELECT id, name, slug FROM communities
        ORDER BY name
    ''').fetchall()
    return [{'id': r['id'], 'name': r['name'] or r['slug'] or r['id']} for r in rows]


def get_communities(filters: dict = None) -> list[dict]:
    """
    Holt Communities aus der communities-Tabelle.

    Args:
        filters: Optional dict mit Filtern:
            - ids: list[str] - Filter nach Community-IDs
            - slugs: list[str] - Filter nach Slugs
            - search_text: str - Suche in Name/Description
            - member_count_min/max: int
            - post_count_min/max: int
            - has_picture: bool
            - sort: str - Sortierung (name, member_count, post_count)
            - sort_order: str - ASC oder DESC
            - limit: int
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

    valid_sorts = {'name': 'name', 'member_count': 'member_count', 'post_count': 'post_count'}
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


def get_communities_with_shared_members(filters: dict) -> list:
    """
    Ermittelt Communities mit gemeinsamen Members.

    Args:
        filters: dict mit:
            - community_ids: list[str] - Die zu vergleichenden Communities
            - min_shared_members: int - Minimum Anzahl gemeinsamer Members
    """
    community_ids = filters.get('community_ids', [])
    min_shared = filters.get('min_shared_members', 1)

    if len(community_ids) < 2:
        return []

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


# ============================================
# MEMBERS
# ============================================

def get_members(filters: dict = None) -> list[dict]:
    """
    Holt Members aus der members-Tabelle.

    Args:
        filters: Optional dict mit Filtern:
            - community_ids: list[str]
            - role: str (legacy) / roles: list[str]
            - is_owner: bool
            - level_min/max: int
            - post_count_min/max: int
            - search_text: str
            - inactive_since_days: int
            - active_in_last_days: int
            - joined_before_days/joined_within_days: int
            - joined_after/joined_before: str (YYYY-MM-DD)
            - has_picture: bool
            - bio_contains: str
            - exclude_member_ids: list[str]
            - sort: str (name, level, post_count, joined_at, last_online)
            - sort_order: str (ASC/DESC)
            - limit: int
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

    # Aktivitäts-Filter
    if filters.get('inactive_since_days'):
        days = int(filters['inactive_since_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND (last_online IS NULL OR last_online < ?)'
        params.append(cutoff)

    if filters.get('active_in_last_days'):
        days = int(filters['active_in_last_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND last_online >= ?'
        params.append(cutoff)

    # Joined-Filter
    if filters.get('joined_before_days'):
        days = int(filters['joined_before_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND joined_at < ?'
        params.append(cutoff)

    if filters.get('joined_within_days'):
        days = int(filters['joined_within_days'])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += ' AND joined_at >= ?'
        params.append(cutoff)

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
        'name': 'name', 'level': 'level', 'post_count': 'post_count',
        'joined': 'joined_at', 'joined_at': 'joined_at',
        'last_online': 'last_online', 'last_active': 'last_online'
    }
    sort_column = valid_sorts.get(sort_field, 'level')
    query += f' ORDER BY {sort_column} {sort_order}'

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

    if filters.get('bio_contains'):
        search = filters['bio_contains'].lower()
        members = [m for m in members if search in (m.get('bio') or '').lower()]

    return members


# ============================================
# POSTS
# ============================================

def get_posts(filters: dict = None) -> list[dict]:
    """
    Holt Posts aus der posts-Tabelle.

    Args:
        filters: Optional dict mit Filtern:
            - community_ids: list[str]
            - author_ids: list[str]
            - likes_min/max: int
            - comments_min/max: int
            - date_from/date_to: str (YYYY-MM-DD)
            - created_within_days: int
            - search_text: str
            - has_content/has_title/has_media: bool
            - title_contains/content_contains: str
            - content_length_min/max: int
            - author_name_contains: str
            - exclude_author_ids: list[str]
            - sort: str (likes, comments, created_at, title)
            - sort_order: str (ASC/DESC)
            - limit: int
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

    # Content-Filter
    if filters.get('has_content'):
        query += " AND content IS NOT NULL AND content != ''"

    if filters.get('has_title'):
        query += " AND title IS NOT NULL AND title != ''"

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

    valid_sorts = {'likes': 'likes', 'comments': 'comments', 'created_at': 'created_at', 'title': 'title'}
    sort_column = valid_sorts.get(sort_field, 'likes')
    query += f' ORDER BY {sort_column} {sort_order}'

    if sort_column != 'created_at':
        query += ', created_at DESC'

    # Limit
    if filters.get('limit'):
        query += ' LIMIT ?'
        params.append(int(filters['limit']))

    rows = db.execute(query, params).fetchall()
    posts = [dict(row) for row in rows]

    # Text-Suche in Python (case-insensitive)
    if filters.get('search_text'):
        search = filters['search_text'].lower()
        posts = [p for p in posts if search in (p.get('title') or '').lower()
                 or search in (p.get('content') or '').lower()]

    if filters.get('title_contains'):
        search = filters['title_contains'].lower()
        posts = [p for p in posts if search in (p.get('title') or '').lower()]

    if filters.get('content_contains'):
        search = filters['content_contains'].lower()
        posts = [p for p in posts if search in (p.get('content') or '').lower()]

    if filters.get('author_name_contains'):
        search = filters['author_name_contains'].lower()
        posts = [p for p in posts if search in (p.get('author_name') or '').lower()]

    return posts


# ============================================
# ENTITIES OVERVIEW (dedupliziert)
# ============================================

def get_entities_stats() -> dict:
    """Holt Statistiken über alle Entitäten"""
    db = get_db()
    return {
        'members': db.execute('SELECT COUNT(*) as c FROM members').fetchone()['c'],
        'posts': db.execute('SELECT COUNT(*) as c FROM posts').fetchone()['c'],
        'communities': db.execute('SELECT COUNT(*) as c FROM communities').fetchone()['c'],
        'raw_fetches': db.execute('SELECT COUNT(*) as c FROM raw_fetches').fetchone()['c']
    }


def get_entities_overview() -> dict:
    """Holt Stats und Sample-Daten für die Entities-Übersicht"""
    db = get_db()
    return {
        'stats': get_entities_stats(),
        'members': db.execute(
            'SELECT * FROM members ORDER BY level DESC, name LIMIT 20'
        ).fetchall(),
        'posts': db.execute(
            'SELECT * FROM posts ORDER BY likes DESC, created_at DESC LIMIT 20'
        ).fetchall(),
        'communities': db.execute('SELECT * FROM communities').fetchall()
    }


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

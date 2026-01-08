"""
Fetch Queue - Queue-Builder und Entity Extraction
"""

import json
from datetime import datetime

from db import get_db, get_latest_fetch, log
from models import Member, Post, Community


# ============================================
# PRIORITÄTEN
# ============================================

PRIORITY_CRITICAL = 0  # Initiale Fetches, ohne die nichts geht
PRIORITY_HIGH = 1      # Primäre Fetches (Members, Posts)
PRIORITY_MEDIUM = 2    # Sekundäre Fetches (Details, Likes)
PRIORITY_LOW = 3       # Tertiäre Fetches (Profile)
PRIORITY_LOWEST = 4    # Erweiterte Fetches (Shared Communities)

# Refresh-Interval in Sekunden (24 Stunden)
REFRESH_INTERVAL = 86400

# Config
FETCH_POST_LIKES = True
FETCH_POST_COMMENTS = True
FETCH_MEMBER_PROFILES = True


# ============================================
# HELPERS
# ============================================

def parse_fetched_at(fetched_at_str) -> datetime | None:
    """Parst fetched_at String zu datetime"""
    if not fetched_at_str:
        return None
    try:
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


# ============================================
# JSON EXTRACTION HELPERS
# ============================================

def extract_member_info(raw_json: str) -> tuple[list[dict], int]:
    """Extrahiert Member-Infos (ID + Slug) und Gesamtseitenzahl aus Members-JSON"""
    members = []
    total_pages = 1

    try:
        data = json.loads(raw_json)
        page_props = data.get('pageProps', {})

        if 'totalPages' in page_props:
            total_pages = int(page_props['totalPages'])

        for user in page_props.get('users', []):
            user_id = user.get('id', '')
            slug = user.get('name', '')
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

        for pt in page_props.get('postTrees', []):
            post = pt.get('post', {})
            group_id = post.get('groupId', '')
            if group_id:
                return group_id

        if page_props.get('groupId'):
            return page_props['groupId']

        group = page_props.get('group', {})
        if group.get('id'):
            return group['id']

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return ''


# ============================================
# TASK BUILDERS
# ============================================

def _build_task_if_needed(entity_type: str, entity_id: str, priority: int,
                          community_id: str, reason_new: str, reason_refresh: str,
                          extra_fields: dict = None) -> list[dict]:
    """
    Generische Task-Erstellung wenn Fetch nötig.
    Reduziert Duplikation in den spezifischen build_*_tasks Funktionen.
    """
    tasks = []
    row = get_latest_fetch(entity_type, entity_id)

    task = {
        'id': generate_task_id(entity_type, community_id, entity_id.replace(f"{community_id}_", "")),
        'type': entity_type,
        'priority': priority,
        'communityId': community_id,
        **(extra_fields or {})
    }

    if row is None:
        task['reason'] = reason_new
        tasks.append(task)
    else:
        fetched_at = parse_fetched_at(row['fetched_at'])
        if needs_refresh(fetched_at):
            task['reason'] = reason_refresh
            task['lastFetchedAt'] = fetched_at.isoformat() if fetched_at else None
            tasks.append(task)

    return tasks


def build_members_tasks(community_id: str) -> tuple[list[dict], list[str]]:
    """Erstellt Tasks für Members-Fetches und gibt neue Member-Slugs zurück"""
    tasks = []
    new_member_slugs = []

    page1_id = f"{community_id}_page_1"
    row = get_latest_fetch('members', page1_id)

    if row is None:
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

    existing_members, total_pages = extract_member_info(raw_json)

    for member in existing_members:
        slug = member.get('slug', '')
        if not slug:
            continue
        entity_id = f"{community_id}_{slug}"
        profile_row = get_latest_fetch('profile', entity_id)
        if profile_row is None:
            new_member_slugs.append(slug)

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

    page1_id = f"{community_id}_page_1"
    row = get_latest_fetch('community_page', page1_id)

    if row is None:
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

    existing_post_ids = extract_post_ids(raw_json)

    for post_id in existing_post_ids:
        entity_id = f"{community_id}_{post_id}"
        details_row = get_latest_fetch('post_details', entity_id)
        if details_row is None:
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
            'entityId': member_slug,
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


# ============================================
# FETCH QUEUE BUILDER
# ============================================

def build_fetch_queue(community_ids: list[str]) -> dict:
    """
    Erstellt die Fetch-Queue nach der Hierarchie:
    1. PRIMÄR: Members + Community Page (Posts)
    2. SEKUNDÄR: Post Details (Kommentare) + Likes
    3. TERTIÄR: Profile für neue Members
    """
    tasks = []

    all_new_post_ids = {}
    all_new_member_slugs = {}
    community_group_ids = {}

    for community_id in community_ids:
        # PHASE 1: PRIMÄRE FETCHES
        members_tasks, new_member_slugs = build_members_tasks(community_id)
        tasks.extend(members_tasks)
        for slug in new_member_slugs:
            all_new_member_slugs[slug] = community_id

        posts_tasks, new_post_ids = build_posts_tasks(community_id)
        tasks.extend(posts_tasks)
        for pid in new_post_ids:
            all_new_post_ids[pid] = community_id

        page1_id = f"{community_id}_page_1"
        row = get_latest_fetch('community_page', page1_id)
        if row:
            group_id = extract_group_id(row['raw_json'])
            if group_id:
                community_group_ids[community_id] = group_id

    # PHASE 2: SEKUNDÄRE FETCHES
    if FETCH_POST_COMMENTS:
        for post_id, community_id in all_new_post_ids.items():
            group_id = community_group_ids.get(community_id, '')
            tasks.extend(build_post_details_tasks(community_id, post_id, group_id))

    if FETCH_POST_LIKES:
        for post_id, community_id in all_new_post_ids.items():
            group_id = community_group_ids.get(community_id, '')
            tasks.extend(build_likes_tasks(community_id, post_id, group_id))

    # PHASE 3: TERTIÄRE FETCHES
    if FETCH_MEMBER_PROFILES:
        for member_slug, community_id in all_new_member_slugs.items():
            tasks.extend(build_profile_tasks(community_id, member_slug))

    tasks.sort(key=lambda t: t['priority'])

    return {
        'tasks': tasks,
        'generatedAt': datetime.now().isoformat(),
        'totalTasks': len(tasks)
    }


def build_fetch_url(entity_type: str, community: str) -> str:
    """URL für Fetch-Task bauen"""
    base = f'https://www.skool.com/{community}'
    urls = {
        'about_page': f'{base}/about',
        'members': f'{base}/members',
        'community_page': base,
    }
    return urls.get(entity_type, base)


# ============================================
# ENTITY EXTRACTION
# ============================================

def extract_entities_from_fetch(raw_fetch_id: int, entity_type: str, entity_id: str, raw_json: str):
    """
    Extrahiert strukturierte Entities aus einem raw_fetch und speichert sie.
    Wird automatisch nach jedem /api/sync aufgerufen.
    """
    db = get_db()

    if entity_type == 'members':
        members = Member.extract_from_raw_json(raw_json, raw_fetch_id, entity_id)
        for member in members:
            db.execute(Member.upsert_sql(), member.to_db_row())

        community = Community.extract_from_members_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    elif entity_type == 'community_page':
        posts = Post.extract_from_community_page(raw_json, raw_fetch_id, entity_id)
        for post in posts:
            db.execute(Post.upsert_sql(), post.to_db_row())

        community = Community.extract_from_community_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    elif entity_type == 'post_details':
        post = Post.extract_from_post_details(raw_json, raw_fetch_id, entity_id)
        if post:
            db.execute(Post.upsert_sql(), post.to_db_row())

    elif entity_type == 'about_page':
        community = Community.extract_from_about_page(raw_json, entity_id, raw_fetch_id)
        if community:
            _upsert_community(db, community)

    db.commit()


def _upsert_community(db, community: Community):
    """Upsert für Community mit Merge-Logik"""
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


def reprocess_all_raw_fetches() -> int:
    """
    Verarbeitet alle raw_fetches neu und extrahiert Entities.
    Nützlich nach Schema-Updates oder bei Datenproblemen.
    """
    db = get_db()

    db.execute('DELETE FROM members')
    db.execute('DELETE FROM posts')
    db.execute('DELETE FROM communities')
    db.commit()

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

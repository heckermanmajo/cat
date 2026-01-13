"""
Extrahiert User, Post, Profile und Leaderboard Entitäten aus Fetches.
Bei Re-Extraktion werden alte Einträge des Fetches überschrieben.
"""
import json
import time
from datetime import datetime
from .fetch import Fetch
from .user import User
from .post import Post
from .profile import Profile
from .leaderboard import Leaderboard
from model import Model


def _iso_to_timestamp(iso_str: str) -> int:
    """Konvertiert ISO-Datum zu Unix-Timestamp. Returns 0 bei Fehler."""
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except:
        return 0

def extract_from_fetch(fetch: Fetch) -> dict:
    """
    Extrahiert Entitäten aus einem Fetch.
    Löscht vorher alle alten Einträge dieses Fetches.
    Returns: {'users': int, 'posts': int, 'profiles': int, 'leaderboard': int, 'leaderboard_applied': int}
    """
    result = {'users': 0, 'posts': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0}
    if fetch.type == 'members':
        result['users'] = _extract_users(fetch)
    elif fetch.type == 'posts':
        result['posts'] = _extract_posts(fetch)
    elif fetch.type == 'profile':
        result['profiles'] = _extract_profile(fetch)
    elif fetch.type == 'leaderboard':
        result['leaderboard'] = _extract_leaderboard(fetch)
        # Auto-apply leaderboard to users
        result['leaderboard_applied'] = apply_leaderboard_to_users(fetch.community_slug)
    return result

def extract_all_fetches() -> dict:
    """Extrahiert aus allen Fetches."""
    totals = {'users': 0, 'posts': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0}
    for fetch in Fetch.all():
        result = extract_from_fetch(fetch)
        totals['users'] += result['users']
        totals['posts'] += result['posts']
        totals['profiles'] += result['profiles']
        totals['leaderboard'] += result['leaderboard']
        totals['leaderboard_applied'] += result['leaderboard_applied']
    return totals

def _extract_users(fetch: Fetch) -> int:
    """Extrahiert Users aus einem members-Fetch."""
    # Alte Einträge dieses Fetches löschen
    Model.connect().execute("DELETE FROM user WHERE fetch_id = ?", [fetch.id])
    Model.connect().commit()

    data = json.loads(fetch.raw_data) if fetch.raw_data else {}
    users_raw = data.get('pageProps', {}).get('users', [])
    now = int(time.time())
    count = 0

    for u in users_raw:
        member = u.get('member', {})
        meta = u.get('metadata', {})
        member_meta = member.get('metadata', {})
        user = User({
            'fetch_id': fetch.id,
            'fetched_at': now,
            'community_slug': fetch.community_slug,
            'skool_id': u.get('id', ''),
            'name': u.get('name', ''),
            'email': u.get('email', ''),
            'first_name': u.get('firstName', ''),
            'last_name': u.get('lastName', ''),
            'skool_created_at': u.get('createdAt', ''),
            'skool_updated_at': u.get('updatedAt', ''),
            'metadata': json.dumps(meta),
            'member_id': member.get('id', ''),
            'member_role': member.get('role', ''),
            'member_group_id': member.get('groupId', ''),
            'member_created_at': _iso_to_timestamp(member.get('createdAt', '')),
            'member_metadata': json.dumps(member_meta),
            'picture_url': meta.get('picture', ''),
            'bio': meta.get('bio', ''),
            # points kommen aus Leaderboard, nicht aus members-Fetch
            'last_active': meta.get('lastOffline', 0) or 0,
            'is_online': meta.get('online', 0) or 0,
        })
        user.save()
        count += 1

    return count

def _extract_posts(fetch: Fetch) -> int:
    """Extrahiert Posts aus einem posts-Fetch."""
    # Alte Einträge dieses Fetches löschen
    Model.connect().execute("DELETE FROM post WHERE fetch_id = ?", [fetch.id])
    Model.connect().commit()

    data = json.loads(fetch.raw_data) if fetch.raw_data else {}
    trees = data.get('pageProps', {}).get('postTrees', [])
    now = int(time.time())
    count = 0

    for tree in trees:
        p = tree.get('post', {})
        u = p.get('user', {})
        meta = p.get('metadata', {})
        skool_id = p.get('id', '')
        root_id = p.get('rootId', '') or ''
        is_toplevel = 1 if (root_id == '' or root_id == skool_id) else 0
        post = Post({
            'fetch_id': fetch.id,
            'fetched_at': now,
            'community_slug': fetch.community_slug,
            'skool_id': skool_id,
            'name': p.get('name', ''),
            'post_type': p.get('postType', ''),
            'group_id': p.get('groupId', ''),
            'user_id': p.get('userId', ''),
            'label_id': p.get('labelId', ''),
            'root_id': root_id,
            'skool_created_at': p.get('createdAt', ''),
            'skool_updated_at': p.get('updatedAt', ''),
            'metadata': json.dumps(meta),
            'is_toplevel': is_toplevel,
            'comments': meta.get('comments', 0) or 0,
            'upvotes': meta.get('upvotes', 0) or 0,
            'user_name': u.get('name', ''),
            'user_metadata': json.dumps(u.get('metadata', {})),
        })
        post.save()
        count += 1

    return count

def _extract_profile(fetch: Fetch) -> int:
    """Extrahiert Profile aus einem profile-Fetch."""
    # Alte Einträge dieses Fetches löschen
    Model.connect().execute("DELETE FROM profile WHERE fetch_id = ?", [fetch.id])
    Model.connect().commit()

    data = json.loads(fetch.raw_data) if fetch.raw_data else {}
    # Profile-Daten kommen aus currentUser oder renderData.user
    u = data.get('pageProps', {}).get('currentUser', {})
    if not u:
        u = data.get('pageProps', {}).get('renderData', {}).get('user', {})
    if not u or not u.get('id'):
        return 0

    now = int(time.time())
    pd = u.get('profileData', {})
    member = pd.get('member', {})

    profile = Profile({
        'fetch_id': fetch.id,
        'fetched_at': now,
        'community_slug': fetch.community_slug,
        'skool_id': u.get('id', ''),
        'name': u.get('name', ''),
        'email': u.get('email', ''),
        'first_name': u.get('firstName', ''),
        'last_name': u.get('lastName', ''),
        'skool_created_at': u.get('createdAt', ''),
        'skool_updated_at': u.get('updatedAt', ''),
        'metadata': json.dumps(u.get('metadata', {})),
        'total_posts': pd.get('totalPosts', 0) or 0,
        'total_followers': pd.get('totalFollowers', 0) or 0,
        'total_following': pd.get('totalFollowing', 0) or 0,
        'total_contributions': pd.get('totalContributions', 0) or 0,
        'total_groups': pd.get('totalGroups', 0) or 0,
        'member_id': member.get('id', ''),
        'member_role': member.get('role', ''),
        'member_metadata': json.dumps(member.get('metadata', {})),
        'groups_member_of': json.dumps(pd.get('groupsMemberOf', [])),
        'groups_created_by_user': json.dumps(pd.get('groupsCreatedByUser', [])),
        'daily_activities': json.dumps(pd.get('dailyActivities', {})),
    })
    profile.save()
    return 1

def _extract_leaderboard(fetch: Fetch) -> int:
    """Extrahiert Leaderboard-Einträge aus einem leaderboard-Fetch."""
    # Alte Einträge dieses Fetches löschen
    Model.connect().execute("DELETE FROM leaderboard WHERE fetch_id = ?", [fetch.id])
    Model.connect().commit()

    data = json.loads(fetch.raw_data) if fetch.raw_data else {}
    # Leaderboard-Daten aus leaderboardsData oder renderData.leaderboard
    lb_data = data.get('pageProps', {}).get('leaderboardsData', {})
    if not lb_data:
        lb_data = data.get('pageProps', {}).get('renderData', {}).get('leaderboard', {})

    users = lb_data.get('users', [])
    now = int(time.time())
    count = 0

    for entry in users:
        lb = Leaderboard({
            'fetch_id': fetch.id,
            'fetched_at': now,
            'community_slug': fetch.community_slug,
            'user_skool_id': entry.get('userId', ''),
            'rank': entry.get('rank', 0) or 0,
            'points': entry.get('points', 0) or 0,
        })
        lb.save()
        count += 1

    return count

def apply_leaderboard_to_users(community_slug: str) -> int:
    """
    Wendet Leaderboard-Daten auf User an.
    Aktualisiert points und leaderboard_applied_at für alle User mit Leaderboard-Eintrag.
    Returns: Anzahl aktualisierter User.
    """
    now = int(time.time())

    # Hole neueste Leaderboard-Einträge pro User (dedupliziert)
    sql = """
        UPDATE user
        SET points = (
            SELECT lb.points FROM leaderboard lb
            WHERE lb.user_skool_id = user.skool_id
            AND lb.community_slug = user.community_slug
            ORDER BY lb.fetched_at DESC
            LIMIT 1
        ),
        leaderboard_applied_at = ?
        WHERE community_slug = ?
        AND EXISTS (
            SELECT 1 FROM leaderboard lb
            WHERE lb.user_skool_id = user.skool_id
            AND lb.community_slug = user.community_slug
        )
    """
    conn = Model.connect()
    cursor = conn.execute(sql, [now, community_slug])
    conn.commit()
    return cursor.rowcount

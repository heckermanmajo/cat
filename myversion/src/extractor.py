"""
Extrahiert User und Post Entitäten aus Fetches.
Bei Re-Extraktion werden alte Einträge des Fetches überschrieben.
"""
import json
import time
from .fetch import Fetch
from .user import User
from .post import Post
from .model import Model

def extract_from_fetch(fetch: Fetch) -> dict:
    """
    Extrahiert Entitäten aus einem Fetch.
    Löscht vorher alle alten Einträge dieses Fetches.
    Returns: {'users': int, 'posts': int} - Anzahl extrahierter Einträge
    """
    if fetch.type == 'members':
        return {'users': _extract_users(fetch), 'posts': 0}
    if fetch.type == 'posts':
        return {'users': 0, 'posts': _extract_posts(fetch)}
    return {'users': 0, 'posts': 0}

def extract_all_fetches() -> dict:
    """Extrahiert aus allen Fetches. Returns: {'users': int, 'posts': int}"""
    totals = {'users': 0, 'posts': 0}
    for fetch in Fetch.all():
        result = extract_from_fetch(fetch)
        totals['users'] += result['users']
        totals['posts'] += result['posts']
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
            'metadata': json.dumps(u.get('metadata', {})),
            'member_id': member.get('id', ''),
            'member_role': member.get('role', ''),
            'member_group_id': member.get('groupId', ''),
            'member_created_at': member.get('createdAt', ''),
            'member_metadata': json.dumps(member.get('metadata', {})),
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
        post = Post({
            'fetch_id': fetch.id,
            'fetched_at': now,
            'community_slug': fetch.community_slug,
            'skool_id': p.get('id', ''),
            'name': p.get('name', ''),
            'post_type': p.get('postType', ''),
            'group_id': p.get('groupId', ''),
            'user_id': p.get('userId', ''),
            'label_id': p.get('labelId', ''),
            'root_id': p.get('rootId', ''),
            'skool_created_at': p.get('createdAt', ''),
            'skool_updated_at': p.get('updatedAt', ''),
            'metadata': json.dumps(p.get('metadata', {})),
            'user_name': u.get('name', ''),
            'user_metadata': json.dumps(u.get('metadata', {})),
        })
        post.save()
        count += 1

    return count

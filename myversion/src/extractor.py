"""
Extrahiert User, Post und Profile Entitäten aus Fetches.
Bei Re-Extraktion werden alte Einträge des Fetches überschrieben.
"""
import json
import time
from .fetch import Fetch
from .user import User
from .post import Post
from .profile import Profile
from model import Model

def extract_from_fetch(fetch: Fetch) -> dict:
    """
    Extrahiert Entitäten aus einem Fetch.
    Löscht vorher alle alten Einträge dieses Fetches.
    Returns: {'users': int, 'posts': int, 'profiles': int}
    """
    if fetch.type == 'members':
        return {'users': _extract_users(fetch), 'posts': 0, 'profiles': 0}
    if fetch.type == 'posts':
        return {'users': 0, 'posts': _extract_posts(fetch), 'profiles': 0}
    if fetch.type == 'profile':
        return {'users': 0, 'posts': 0, 'profiles': _extract_profile(fetch)}
    return {'users': 0, 'posts': 0, 'profiles': 0}

def extract_all_fetches() -> dict:
    """Extrahiert aus allen Fetches."""
    totals = {'users': 0, 'posts': 0, 'profiles': 0}
    for fetch in Fetch.all():
        result = extract_from_fetch(fetch)
        totals['users'] += result['users']
        totals['posts'] += result['posts']
        totals['profiles'] += result['profiles']
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
            'member_created_at': member.get('createdAt', ''),
            'member_metadata': json.dumps(member_meta),
            'picture_url': meta.get('picture', ''),
            'bio': meta.get('bio', ''),
            'points': member_meta.get('points', 0) or 0,
            'level': member_meta.get('level', 0) or 0,
            'last_active': member.get('lastOffline', ''),
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

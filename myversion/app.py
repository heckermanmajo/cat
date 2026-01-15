from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import json
from model import Model
from src.config_entry import ConfigEntry
from src.fetch_task import FetchTask
from src.fetch import Fetch
from src.user import User
from src.post import Post
from src.profile import Profile
from src.leaderboard import Leaderboard
from src.like import Like
from src.other_community import OtherCommunity
from src import extractor
from src.members_filter import MembersFilter

app = Flask(__name__, static_folder='static')
CORS(app)

# DB init
Model.connect('app.db')
ConfigEntry.register(app)
Fetch.register(app)
User.register(app)
Post.register(app)
Profile.register(app)
Leaderboard.register(app)
Like.register(app)
OtherCommunity.register(app)

@app.route('/api/fetch-tasks')
def get_fetch_tasks(): return jsonify([t.to_dict() for t in FetchTask.generateFetchTasks()])

def _extract_pagination(data: dict, fetch_type: str) -> tuple[int, int]:
    """Extrahiert total_items und total_pages aus pageProps."""
    pp = data.get('pageProps', {})
    total = pp.get('total', 0) or 0
    if fetch_type == 'members':
        total_pages = pp.get('totalPages', 0) or 0
    elif fetch_type == 'posts':
        # Posts haben kein totalPages, wir berechnen es (20 items pro Seite)
        total_pages = (total + 19) // 20 if total > 0 else 0
    elif fetch_type == 'leaderboard':
        # Leaderboard: Daten in leaderboardsData oder renderData.leaderboard
        lb = pp.get('leaderboardsData', {}) or pp.get('renderData', {}).get('leaderboard', {})
        total = len(lb.get('users', []))
        # Schätze total_pages basierend auf limit (typisch 20)
        limit = lb.get('limit', 20) or 20
        total_pages = (total + limit - 1) // limit if total > 0 else 1
    else:
        total_pages = 0
    return total, total_pages

@app.route('/api/fetch-result', methods=['POST'])
def post_fetch_result():
    """Empfängt Results vom Plugin und speichert sie als Fetch."""
    results = request.json.get('results', [])
    saved = []
    extracted = {'users': 0, 'posts': 0, 'comments': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0, 'other_communities': 0, 'likes': 0}
    for r in results:
        task = r.get('task', {})
        result = r.get('result', {})
        data = result.get('data', {})
        fetch_type = task.get('type', '')
        total_items, total_pages = _extract_pagination(data, fetch_type)
        f = Fetch({
            'type': fetch_type,
            'community_slug': task.get('communitySlug', ''),
            'page_param': task.get('pageParam', 1),
            'user_skool_id': task.get('userSkoolHexId', ''),
            'post_skool_id': task.get('postSkoolHexId', ''),
            'status': 'ok' if result.get('ok') else 'error',
            'error_message': result.get('error', ''),
            'raw_data': json.dumps(data),
            'total_items': total_items,
            'total_pages': total_pages,
        })
        f.save()
        saved.append(f.to_dict())
        # Auto-Extraktion
        ex = extractor.extract_from_fetch(f)
        extracted['users'] += ex['users']
        extracted['posts'] += ex['posts']
        extracted['comments'] += ex['comments']
        extracted['profiles'] += ex['profiles']
        extracted['leaderboard'] += ex['leaderboard']
        extracted['leaderboard_applied'] += ex['leaderboard_applied']
        extracted['other_communities'] += ex['other_communities']
        extracted['likes'] += ex['likes']
    return jsonify({'saved': len(saved), 'fetches': saved, 'extracted': extracted}), 201

@app.route('/api/extract/<int:fetch_id>', methods=['POST'])
def extract_fetch(fetch_id):
    """Manuell: Extrahiert User/Posts aus einem Fetch."""
    f = Fetch.by_id(fetch_id)
    if not f: return 'Not found', 404
    result = extractor.extract_from_fetch(f)
    return jsonify(result)

@app.route('/api/extract-all', methods=['POST'])
def extract_all():
    """Manuell: Extrahiert aus allen Fetches."""
    result = extractor.extract_all_fetches()
    return jsonify(result)

@app.route('/api/extract-info')
def extract_info():
    """Gibt Anzahl der Fetches zurück für Batch-Verarbeitung."""
    count = Fetch.count()
    return jsonify({'total': count})

@app.route('/api/extract-batch', methods=['POST'])
def extract_batch():
    """Extrahiert eine Batch von Fetches (offset/limit). Sortiert nach Typ für korrekte Reihenfolge."""
    offset = request.json.get('offset', 0)
    limit = request.json.get('limit', 50)
    # Reihenfolge: members(1) -> posts(2) -> comments(3) -> profile(4) -> leaderboard(5) -> community_about(6)
    fetches = Fetch.get_list(
        """SELECT * FROM fetch ORDER BY
           CASE type
               WHEN 'members' THEN 1
               WHEN 'posts' THEN 2
               WHEN 'comments' THEN 3
               WHEN 'profile' THEN 4
               WHEN 'leaderboard' THEN 5
               WHEN 'community_about' THEN 6
               ELSE 7
           END, id
           LIMIT ? OFFSET ?""",
        [limit, offset]
    )
    result = {'users': 0, 'posts': 0, 'comments': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0, 'other_communities': 0, 'likes': 0}
    Model.begin_batch()
    for f in fetches:
        ex = extractor.extract_from_fetch(f)
        result['users'] += ex['users']
        result['posts'] += ex['posts']
        result['comments'] += ex['comments']
        result['profiles'] += ex['profiles']
        result['leaderboard'] += ex['leaderboard']
        result['leaderboard_applied'] += ex['leaderboard_applied']
        result['other_communities'] += ex['other_communities']
        result['likes'] += ex['likes']
    Model.end_batch()
    return jsonify({'extracted': result, 'processed': len(fetches)})

@app.route('/api/apply-leaderboard', methods=['POST'])
def apply_leaderboard():
    """Wendet Leaderboard-Punkte auf User an."""
    community = ConfigEntry.getByKey('current_community')
    if not community or not community.value:
        return jsonify({'error': 'No community selected'}), 400
    updated = extractor.apply_leaderboard_to_users(community.value)
    return jsonify({'updated': updated, 'community': community.value})

@app.route('/api/user/filter', methods=['POST'])
def filter_users():
    """Filter users with include/exclude conditions, search, and sorting."""
    data = request.json or {}
    # Add current community if not provided
    if not data.get('communitySlug'):
        community = ConfigEntry.getByKey('current_community')
        data['communitySlug'] = community.value if community else ''
    f = MembersFilter(data)
    users = User.filtered(f)
    return jsonify([u.to_dict() for u in users])

@app.route('/api/post/latest')
def get_posts_latest():
    """Get latest post per skool_id (deduplicated)."""
    posts = Post.get_list(
        """SELECT * FROM post WHERE id IN (
            SELECT MAX(id) FROM post GROUP BY skool_id
        ) ORDER BY id DESC"""
    )
    return jsonify([p.to_dict() for p in posts])

@app.route('/api/user/<int:user_id>/posts')
def get_user_posts(user_id):
    """Get all posts by a user (via their skool_id)."""
    user = User.by_id(user_id)
    if not user: return 'User not found', 404
    posts = Post.get_list(
        "SELECT * FROM post WHERE user_id = ? ORDER BY created_at DESC",
        [user.skool_id]
    )
    return jsonify([p.to_dict() for p in posts])

@app.route('/api/post/by-users', methods=['POST'])
def get_posts_by_users():
    """Get posts filtered by user skool_ids (deduplicated: latest per skool_id)."""
    skool_ids = request.json.get('skool_ids', [])
    if not skool_ids:
        return jsonify([])
    # Batch to avoid SQLite variable limit
    posts = []
    batch_size = 400
    for i in range(0, len(skool_ids), batch_size):
        batch = skool_ids[i:i + batch_size]
        placeholders = ','.join(['?'] * len(batch))
        posts.extend(Post.get_list(
            f"""SELECT * FROM post WHERE user_id IN ({placeholders})
                AND id IN (SELECT MAX(id) FROM post GROUP BY skool_id)
                ORDER BY id DESC""",
            batch
        ))
    # Sort all results by id desc (latest first)
    posts.sort(key=lambda p: p.id, reverse=True)
    return jsonify([p.to_dict() for p in posts])

@app.route('/api/user/<int:user_id>/communities')
def get_user_communities(user_id):
    """Get all communities where a user (by skool_id) is a member."""
    user = User.by_id(user_id)
    if not user: return 'User not found', 404
    rows = Model.query(
        "SELECT DISTINCT community_slug FROM user WHERE skool_id = ? AND community_slug != ''",
        [user.skool_id]
    )
    return jsonify([r['community_slug'] for r in rows])

@app.route('/api/user/<int:user_id>/profile-communities')
def get_user_profile_communities(user_id):
    """Get all communities from profile.groups_member_of (more complete than user table)."""
    user = User.by_id(user_id)
    if not user: return 'User not found', 404
    # Get latest profile for this user
    profiles = Profile.get_list(
        "SELECT * FROM profile WHERE skool_id = ? ORDER BY fetched_at DESC LIMIT 1",
        [user.skool_id]
    )
    if not profiles:
        return jsonify([])
    profile = profiles[0]
    groups = json.loads(profile.groups_member_of) if profile.groups_member_of else []
    # Return list of {slug, name} objects
    result = []
    for g in groups:
        slug = g.get('name', '')
        meta = g.get('metadata', {})
        display_name = meta.get('displayName', '') or slug
        if slug:
            result.append({'slug': slug, 'name': display_name})
    return jsonify(result)

@app.route('/api/user/<int:user_id>/liked-posts')
def get_user_liked_posts(user_id):
    """Get all posts that a user has liked."""
    user = User.by_id(user_id)
    if not user: return 'User not found', 404
    # Get all post_skool_ids this user has liked
    likes = Like.get_list(
        "SELECT DISTINCT post_skool_id FROM like WHERE user_skool_id = ?",
        [user.skool_id]
    )
    if not likes:
        return jsonify([])
    # Get the posts (latest version per skool_id)
    post_ids = [l.post_skool_id for l in likes]
    posts = []
    batch_size = 400
    for i in range(0, len(post_ids), batch_size):
        batch = post_ids[i:i + batch_size]
        placeholders = ','.join(['?'] * len(batch))
        posts.extend(Post.get_list(
            f"""SELECT * FROM post WHERE skool_id IN ({placeholders})
                AND id IN (SELECT MAX(id) FROM post GROUP BY skool_id)""",
            batch
        ))
    posts.sort(key=lambda p: p.id, reverse=True)
    return jsonify([p.to_dict() for p in posts])

@app.route('/api/shared-communities', methods=['POST'])
def get_shared_communities():
    """Get communities shared by given skool_ids, with user counts, sorted descending."""
    skool_ids = request.json.get('skool_ids', [])
    if not skool_ids:
        return jsonify([])
    placeholders = ','.join(['?'] * len(skool_ids))
    rows = Model.query(
        f"""SELECT community_slug, COUNT(DISTINCT skool_id) as user_count
            FROM user
            WHERE skool_id IN ({placeholders}) AND community_slug != ''
            GROUP BY community_slug
            ORDER BY user_count DESC""",
        skool_ids
    )
    return jsonify(rows)

@app.route('/api/other-communities')
def get_other_communities():
    """Get all discovered communities from profile fetches, with calculated shared_user_count."""
    # Calculate counts from profiles (DISTINCT skool_ids per community)
    profiles = Model.query("SELECT skool_id, groups_member_of FROM profile WHERE groups_member_of != ''")
    slug_users = {}  # slug -> set of skool_ids
    for p in profiles:
        groups = json.loads(p['groups_member_of']) if p['groups_member_of'] else []
        if not groups:
            continue
        for g in groups:
            slug = g.get('name', '')
            if slug:
                if slug not in slug_users:
                    slug_users[slug] = set()
                slug_users[slug].add(p['skool_id'])

    # Get all OtherCommunities and add calculated count
    communities = OtherCommunity.get_list("SELECT * FROM othercommunity", [])
    result = []
    for c in communities:
        data = c.to_dict()
        data['shared_user_count'] = len(slug_users.get(c.slug, set()))
        result.append(data)

    # Sort by shared_user_count desc
    result.sort(key=lambda x: -x['shared_user_count'])
    return jsonify(result)

@app.route('/api/communities/by-users', methods=['POST'])
def get_communities_by_users():
    """Get OtherCommunities where selected users are members, with selection and global count."""
    skool_ids = request.json.get('skool_ids', [])
    if not skool_ids:
        return jsonify([])

    # Calculate global shared_user_count from ALL profiles
    all_profiles = Model.query("SELECT skool_id, groups_member_of FROM profile WHERE groups_member_of != ''")
    global_slug_users = {}  # slug -> set of skool_ids
    for p in all_profiles:
        groups = json.loads(p['groups_member_of']) if p['groups_member_of'] else []
        if not groups:
            continue
        for g in groups:
            slug = g.get('name', '')
            if slug:
                if slug not in global_slug_users:
                    global_slug_users[slug] = set()
                global_slug_users[slug].add(p['skool_id'])

    # Count how many SELECTED users are in each community
    skool_ids_set = set(skool_ids)
    selection_counts = {}  # slug -> count of selected users
    for slug, users in global_slug_users.items():
        count = len(users & skool_ids_set)
        if count > 0:
            selection_counts[slug] = count

    if not selection_counts:
        return jsonify([])

    # Get OtherCommunity data in batches
    communities = []
    slugs = list(selection_counts.keys())
    batch_size = 400
    for i in range(0, len(slugs), batch_size):
        batch = slugs[i:i + batch_size]
        placeholders = ','.join(['?'] * len(batch))
        communities.extend(OtherCommunity.get_list(
            f"SELECT * FROM othercommunity WHERE slug IN ({placeholders})",
            batch
        ))

    # Build result with calculated counts
    result = []
    for c in communities:
        data = c.to_dict()
        data['selection_count'] = selection_counts.get(c.slug, 0)
        data['shared_user_count'] = len(global_slug_users.get(c.slug, set()))
        result.append(data)

    # Sort by selection_count desc, then shared_user_count desc
    result.sort(key=lambda x: (-x['selection_count'], -x['shared_user_count']))
    return jsonify(result)

@app.route('/api/activity/community')
def get_community_activity():
    """Community-wide activity: posts and comments per day."""
    community = request.args.get('community') or (ConfigEntry.getByKey('current_community') or {}).value or ''
    days = int(request.args.get('days', 90))

    from datetime import datetime, timedelta
    today = datetime.now().date()
    day_labels = [(today - timedelta(days=i)).isoformat() for i in range(days-1, -1, -1)]

    # Posts per day (is_toplevel=1)
    posts_sql = """
        SELECT DATE(skool_created_at) as day, COUNT(*) as cnt
        FROM post WHERE community_slug = ? AND is_toplevel = 1
        AND DATE(skool_created_at) >= DATE('now', ?)
        GROUP BY DATE(skool_created_at)
    """
    posts_rows = Model.query(posts_sql, [community, f'-{days} days'])
    posts_map = {r['day']: r['cnt'] for r in posts_rows}

    # Comments per day (is_toplevel=0)
    comments_sql = """
        SELECT DATE(skool_created_at) as day, COUNT(*) as cnt
        FROM post WHERE community_slug = ? AND is_toplevel = 0
        AND DATE(skool_created_at) >= DATE('now', ?)
        GROUP BY DATE(skool_created_at)
    """
    comments_rows = Model.query(comments_sql, [community, f'-{days} days'])
    comments_map = {r['day']: r['cnt'] for r in comments_rows}

    # New members per day
    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
    members_sql = """
        SELECT DATE(member_created_at, 'unixepoch') as day, COUNT(DISTINCT skool_id) as cnt
        FROM user WHERE community_slug = ? AND member_created_at >= ?
        GROUP BY DATE(member_created_at, 'unixepoch')
    """
    members_rows = Model.query(members_sql, [community, cutoff])
    members_map = {r['day']: r['cnt'] for r in members_rows}

    return jsonify({
        'days': day_labels,
        'posts': [posts_map.get(d, 0) for d in day_labels],
        'comments': [comments_map.get(d, 0) for d in day_labels],
        'new_members': [members_map.get(d, 0) for d in day_labels]
    })

@app.route('/api/database/overview')
def database_overview():
    """Returns all tables with their entry counts."""
    tables = Model.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    result = []
    for t in tables:
        name = t['name']
        count = Model.query(f"SELECT COUNT(*) as c FROM {name}")[0]['c']
        result.append({'name': name, 'count': count})
    result.sort(key=lambda x: -x['count'])
    return jsonify(result)

@app.route('/api/activity/members', methods=['POST'])
def get_members_activity():
    """Member activity: Wochentag x Stunde Heatmap - wann sind Members aktiv (Posts + Comments)."""
    skool_ids = request.json.get('skool_ids', [])
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

    empty_matrix = [[0]*24 for _ in range(7)]
    if not skool_ids:
        return jsonify({'weekdays': weekdays, 'activity_matrix': empty_matrix})

    def batch_query(sql_template, ids, batch_size=400):
        results = []
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = sql_template.replace('__IDS__', placeholders)
            results.extend(Model.query(sql, batch))
        return results

    # Alle Posts + Comments: Wochentag x Stunde (aus skool_created_at)
    activity_sql = """
        SELECT CAST(strftime('%w', skool_created_at) AS INTEGER) as dow,
               CAST(strftime('%H', skool_created_at) AS INTEGER) as hour,
               COUNT(*) as cnt
        FROM post WHERE user_id IN (__IDS__) AND skool_created_at != ''
        GROUP BY dow, hour
    """
    rows = batch_query(activity_sql, skool_ids)
    activity_matrix = [[0]*24 for _ in range(7)]
    for r in rows:
        if r['dow'] is not None and r['hour'] is not None:
            weekday = (r['dow'] - 1) % 7  # %w: 0=Sunday -> 0=Monday
            activity_matrix[weekday][r['hour']] += r['cnt']

    return jsonify({'weekdays': weekdays, 'activity_matrix': activity_matrix})

@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('static', filename)

if __name__ == '__main__': app.run(debug=True, port=3000, threaded=False)

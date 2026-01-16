from flask import jsonify, request
from datetime import datetime, timedelta
from model import Model
from src.config_entry import ConfigEntry
from src.user import User
from src.members_filter import MembersFilter


def register(app):
    # === Activity/Statistics ===

    @app.route('/api/activity/community')
    def get_community_activity():
        """Community-wide activity: posts and comments per day."""
        c = ConfigEntry.getByKey('current_community')
        community = request.args.get('community') or (c.value if c else '')
        if not community:
            return jsonify({'days': [], 'posts': [], 'comments': [], 'new_members': []})
        days = int(request.args.get('days', 90))
        today = datetime.now().date()
        day_labels = [(today - timedelta(days=i)).isoformat() for i in range(days-1, -1, -1)]

        posts_sql = """
            SELECT DATE(skool_created_at) as day, COUNT(*) as cnt
            FROM post WHERE community_slug = ? AND is_toplevel = 1
            AND DATE(skool_created_at) >= DATE('now', ?)
            GROUP BY DATE(skool_created_at)
        """
        posts_rows = Model.query(posts_sql, [community, f'-{days} days'])
        posts_map = {r['day']: r['cnt'] for r in posts_rows}

        comments_sql = """
            SELECT DATE(skool_created_at) as day, COUNT(*) as cnt
            FROM post WHERE community_slug = ? AND is_toplevel = 0
            AND DATE(skool_created_at) >= DATE('now', ?)
            GROUP BY DATE(skool_created_at)
        """
        comments_rows = Model.query(comments_sql, [community, f'-{days} days'])
        comments_map = {r['day']: r['cnt'] for r in comments_rows}

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
                weekday = (r['dow'] - 1) % 7
                activity_matrix[weekday][r['hour']] += r['cnt']

        return jsonify({'weekdays': weekdays, 'activity_matrix': activity_matrix})

    # === Graph/Visualization ===

    @app.route('/api/graph/interactions', methods=['GET', 'POST'])
    def get_graph_interactions():
        """Graph-Daten: Knoten (User mit Bild) + Kanten (Likes, Comments zum Post-Autor)."""
        empty_result = {'nodes': [], 'like_edges': [], 'comment_edges': []}
        # POST: skool_ids direkt übergeben (für gefilterte Members)
        if request.method == 'POST':
            data = request.json or {}
            skool_ids = data.get('skool_ids', [])
            community = data.get('community', '')
            if not community:
                c = ConfigEntry.getByKey('current_community')
                community = c.value if c else ''
            if not community:
                return jsonify(empty_result)
            # Knoten aus übergebenen skool_ids laden (dedupliziert)
            if skool_ids:
                users_raw = []
                batch_size = 400
                for i in range(0, len(skool_ids), batch_size):
                    batch = skool_ids[i:i + batch_size]
                    placeholders = ','.join(['?'] * len(batch))
                    users_raw.extend(User.get_list(
                        f"SELECT * FROM user WHERE skool_id IN ({placeholders}) AND community_slug = ?",
                        batch + [community]
                    ))
                # Deduplizieren nach skool_id (nur ersten behalten)
                seen = set()
                users = []
                for u in users_raw:
                    if u.skool_id not in seen:
                        seen.add(u.skool_id)
                        users.append(u)
            else:
                users = []
        else:
            # GET: Alle User der Community (alte Logik)
            community = request.args.get('community')
            if not community:
                c = ConfigEntry.getByKey('current_community')
                community = c.value if c else ''
            users = User.filtered(MembersFilter({'communitySlug': community}))

        nodes = [{
            'id': u.skool_id,
            'name': u.name,
            'picture': f'/api/image/{u.skool_id}' if u.picture_url else None,
            'role': u.member_role
        } for u in users]
        user_ids = set(u.skool_id for u in users)

        like_rows = Model.query("""
            SELECT l.user_skool_id as source, p.user_id as target, COUNT(*) as weight
            FROM like l
            JOIN (SELECT skool_id, user_id FROM post WHERE id IN
                  (SELECT MAX(id) FROM post GROUP BY skool_id)) p
            ON l.post_skool_id = p.skool_id
            WHERE l.community_slug = ?
            GROUP BY l.user_skool_id, p.user_id
        """, [community])
        like_edges = [r for r in like_rows if r['source'] in user_ids and r['target'] in user_ids and r['source'] != r['target']]

        comment_rows = Model.query("""
            SELECT c.user_id as source, p.user_id as target, COUNT(*) as weight
            FROM post c
            JOIN (SELECT skool_id, user_id FROM post WHERE is_toplevel = 1) p
            ON c.root_id = p.skool_id
            WHERE c.is_toplevel = 0 AND c.community_slug = ?
            GROUP BY c.user_id, p.user_id
        """, [community])
        comment_edges = [r for r in comment_rows if r['source'] in user_ids and r['target'] in user_ids and r['source'] != r['target']]

        return jsonify({
            'nodes': nodes,
            'like_edges': like_edges,
            'comment_edges': comment_edges
        })

    # === Database Overview ===

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

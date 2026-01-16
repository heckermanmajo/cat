from flask import jsonify, request
import json
from model import Model
from src.config_entry import ConfigEntry
from src.fetch_task import FetchTask, FetchStaleInformation
from src.fetch import Fetch
from src import extractor


def _extract_pagination(data: dict, fetch_type: str) -> tuple[int, int]:
    """Extrahiert total_items und total_pages aus pageProps."""
    pp = data.get('pageProps', {})
    total = pp.get('total', 0) or 0
    if fetch_type == 'members':
        total_pages = pp.get('totalPages', 0) or 0
    elif fetch_type == 'posts':
        total_pages = (total + 19) // 20 if total > 0 else 0
    elif fetch_type == 'leaderboard':
        lb = pp.get('leaderboardsData', {}) or pp.get('renderData', {}).get('leaderboard', {})
        total = len(lb.get('users', []))
        limit = lb.get('limit', 20) or 20
        total_pages = (total + limit - 1) // limit if total > 0 else 1
    else:
        total_pages = 0
    return total, total_pages


def register(app):
    @app.route('/api/fetch-tasks')
    def get_fetch_tasks():
        return jsonify([t.to_dict() for t in FetchTask.generateFetchTasks()])

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
            if f.status == 'ok':
                ex = extractor.extract_from_fetch(f)
            else:
                ex = {'users': 0, 'posts': 0, 'comments': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0, 'other_communities': 0, 'likes': 0}
            extracted['users'] += ex['users']
            extracted['posts'] += ex['posts']
            extracted['comments'] += ex['comments']
            extracted['profiles'] += ex['profiles']
            extracted['leaderboard'] += ex['leaderboard']
            extracted['leaderboard_applied'] += ex['leaderboard_applied']
            extracted['other_communities'] += ex['other_communities']
            extracted['likes'] += ex['likes']
        return jsonify({'saved': len(saved), 'fetches': saved, 'extracted': extracted}), 201

    @app.route('/api/fetch-debug')
    def get_fetch_debug():
        """Debug: Zeigt letzte Fetches und warum Tasks generiert werden."""
        import time
        now = int(time.time())
        recent = Fetch.get_list("SELECT * FROM fetch ORDER BY id DESC LIMIT 10")
        thresholds = {}
        for t in ['members', 'posts', 'profile', 'comments', 'likes', 'leaderboard']:
            hours = FetchStaleInformation.get_stale_hours(t)
            thresholds[t] = {'hours': hours, 'cutoff': now - (hours * 3600)}
        community = ConfigEntry.getByKey('current_community')
        slug = community.value if community else ''
        valid_counts = {}
        for t in thresholds:
            rows = Model.query(
                "SELECT COUNT(*) as c FROM fetch WHERE type = ? AND community_slug = ? AND status = 'ok' AND created_at > ?",
                [t, slug, thresholds[t]['cutoff']]
            )
            valid_counts[t] = rows[0]['c'] if rows else 0
        recent_clean = []
        for f in recent:
            d = f.to_dict()
            if d.get('raw_data'):
                d['raw_data'] = d['raw_data'][:100] + '...' if len(d['raw_data']) > 100 else d['raw_data']
            recent_clean.append(d)
        return jsonify({
            'current_community': slug,
            'now': now,
            'thresholds': thresholds,
            'valid_fetch_counts': valid_counts,
            'recent_fetches': recent_clean
        })

    @app.route('/api/reset-failed-about', methods=['POST'])
    def reset_failed_about():
        """Reset about_fetched for communities where fetch failed."""
        from src.other_community import OtherCommunity
        failed = Fetch.get_list(
            "SELECT DISTINCT community_slug FROM fetch WHERE type = 'community_about' AND status = 'error'"
        )
        slugs = [f.community_slug for f in failed]
        if not slugs:
            return jsonify({'reset': 0, 'message': 'No failed community_about fetches found'})
        placeholders = ','.join(['?'] * len(slugs))
        Model.query(f"UPDATE othercommunity SET about_fetched = 0 WHERE slug IN ({placeholders})", slugs)
        Model.query(f"DELETE FROM fetch WHERE type = 'community_about' AND status = 'error'")
        return jsonify({'reset': len(slugs), 'slugs': slugs})

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

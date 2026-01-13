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
    extracted = {'users': 0, 'posts': 0, 'profiles': 0, 'leaderboard': 0, 'leaderboard_applied': 0}
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
        extracted['profiles'] += ex['profiles']
        extracted['leaderboard'] += ex['leaderboard']
        extracted['leaderboard_applied'] += ex['leaderboard_applied']
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

@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('static', filename)

if __name__ == '__main__': app.run(debug=True, port=3000)

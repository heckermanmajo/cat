from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import json
from model import Model
from src.config_entry import ConfigEntry
from src.fetch_task import FetchTask
from src.fetch import Fetch

app = Flask(__name__, static_folder='static')
CORS(app)

# DB init
Model.connect('app.db')
ConfigEntry.register(app)
Fetch.register(app)

@app.route('/api/fetch-tasks')
def get_fetch_tasks(): return jsonify([t.to_dict() for t in FetchTask.generateFetchTasks()])

@app.route('/api/fetch-result', methods=['POST'])
def post_fetch_result():
    """Empfängt Results vom Plugin und speichert sie als Fetch."""
    results = request.json.get('results', [])
    saved = []
    for r in results:
        task = r.get('task', {})
        result = r.get('result', {})
        f = Fetch({
            'type': task.get('type', ''),
            'community_slug': task.get('communitySlug', ''),
            'page_param': task.get('pageParam', 1),
            'status': 'ok' if result.get('ok') else 'error',
            'error_message': result.get('error', ''),
            'raw_data': json.dumps(result.get('data', {}))
        })
        f.save()
        saved.append(f.to_dict())
    return jsonify({'saved': len(saved), 'fetches': saved}), 201

@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('static', filename)

if __name__ == '__main__': app.run(debug=True, port=3000)

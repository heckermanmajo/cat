from flask import Flask, send_from_directory, request
from flask_cors import CORS
from model import Model
from src.config_entry import ConfigEntry
from src.fetch import Fetch
from src.user import User
from src.post import Post
from src.profile import Profile
from src.leaderboard import Leaderboard
from src.like import Like
from src.other_community import OtherCommunity
from routes import fetch_and_extract_routes, query_routes, stats_routes, image_routes, log_routes

app = Flask(__name__, static_folder='static')
CORS(app)

# DB init
Model.connect('app.db')

# Entity-Routes (CRUD per Entity)
ConfigEntry.register(app)
Fetch.register(app)
User.register(app)
Post.register(app)
Profile.register(app)
Leaderboard.register(app)
Like.register(app)
OtherCommunity.register(app)

# Domain-Routes
fetch_and_extract_routes.register(app)
query_routes.register(app)
stats_routes.register(app)
image_routes.register(app)
log_routes.register(app)

@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('static', filename)

@app.errorhandler(404)
def not_found(e):
    from routes.log_routes import log
    log(f'404 Not Found: {request.path}', 'ERROR')
    return f'Not Found: {request.path}', 404

@app.errorhandler(500)
def server_error(e):
    from routes.log_routes import log
    log(f'500 Server Error: {request.path} - {str(e)}', 'ERROR')
    return f'Server Error: {str(e)}', 500

if __name__ == '__main__':
    from routes.log_routes import log
    log('App started on port 3000', 'INFO')
    app.run(debug=True, port=3000, threaded=True)

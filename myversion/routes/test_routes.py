from flask import jsonify, request
from model import Model


def register(app):
    """Test utility endpoints for setting up test data."""

    @app.route('/api/test/reset', methods=['POST'])
    def test_reset():
        """Clear all data from the database. Used for test setup."""
        tables = ['user', 'post', 'fetch', 'like', 'profile', 'othercommunity', 'leaderboard']
        conn = Model.connect()
        for table in tables:
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass  # Table might not exist
        conn.commit()
        return jsonify({'status': 'ok', 'cleared': tables})

    @app.route('/api/test/bulk-users', methods=['POST'])
    def test_bulk_users():
        """Insert multiple users at once for test efficiency."""
        from src.user import User
        users = request.json.get('users', [])
        Model.begin_batch()
        created = []
        for data in users:
            u = User(data)
            u.save()
            created.append(u.id)
        Model.end_batch()
        return jsonify({'status': 'ok', 'created': len(created), 'ids': created})

    @app.route('/api/test/bulk-posts', methods=['POST'])
    def test_bulk_posts():
        """Insert multiple posts at once for test efficiency."""
        from src.post import Post
        posts = request.json.get('posts', [])
        Model.begin_batch()
        created = []
        for data in posts:
            p = Post(data)
            p.save()
            created.append(p.id)
        Model.end_batch()
        return jsonify({'status': 'ok', 'created': len(created), 'ids': created})

    @app.route('/api/test/bulk-likes', methods=['POST'])
    def test_bulk_likes():
        """Insert multiple likes at once for test efficiency."""
        from src.like import Like
        likes = request.json.get('likes', [])
        Model.begin_batch()
        created = []
        for data in likes:
            lk = Like(data)
            lk.save()
            created.append(lk.id)
        Model.end_batch()
        return jsonify({'status': 'ok', 'created': len(created), 'ids': created})

    @app.route('/api/test/bulk-profiles', methods=['POST'])
    def test_bulk_profiles():
        """Insert multiple profiles at once for test efficiency."""
        from src.profile import Profile
        profiles = request.json.get('profiles', [])
        Model.begin_batch()
        created = []
        for data in profiles:
            p = Profile(data)
            p.save()
            created.append(p.id)
        Model.end_batch()
        return jsonify({'status': 'ok', 'created': len(created), 'ids': created})

    @app.route('/api/test/bulk-fetches', methods=['POST'])
    def test_bulk_fetches():
        """Insert multiple fetch records at once."""
        from src.fetch import Fetch
        fetches = request.json.get('fetches', [])
        Model.begin_batch()
        created = []
        for data in fetches:
            f = Fetch(data)
            f.save()
            created.append(f.id)
        Model.end_batch()
        return jsonify({'status': 'ok', 'created': len(created), 'ids': created})

    @app.route('/api/test/set-community', methods=['POST'])
    def test_set_community():
        """Set the current community for testing."""
        from src.config_entry import ConfigEntry
        slug = request.json.get('slug', '')
        entry = ConfigEntry.getByKey('current_community')
        if entry:
            entry.value = slug
            entry.save()
        else:
            entry = ConfigEntry({'key': 'current_community', 'value': slug})
            entry.save()
        return jsonify({'status': 'ok', 'community': slug})

from flask import jsonify, request, Response
import json
import csv
import io
from model import Model
from src.config_entry import ConfigEntry
from src.user import User
from src.post import Post
from src.profile import Profile
from src.like import Like
from src.other_community import OtherCommunity
from src.members_filter import MembersFilter


def register(app):
    # === User Routes ===

    @app.route('/api/user/filter', methods=['POST'])
    def filter_users():
        """Filter users with include/exclude conditions, search, and sorting."""
        data = request.json or {}
        if not data.get('communitySlug'):
            community = ConfigEntry.getByKey('current_community')
            data['communitySlug'] = community.value if community else ''
        f = MembersFilter(data)
        users = User.filtered(f)
        return jsonify([{k: v for k, v in u.to_dict().items() if k not in ('metadata', 'member_metadata')} for u in users])

    @app.route('/api/user/export-csv', methods=['POST'])
    def export_users_csv():
        """Export filtered users as CSV."""
        data = request.json or {}
        if not data.get('communitySlug'):
            community = ConfigEntry.getByKey('current_community')
            data['communitySlug'] = community.value if community else ''
        f = MembersFilter(data)
        users = User.filtered(f)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['name', 'first_name', 'last_name', 'email', 'member_role', 'points', 'joined', 'last_active', 'community', 'skool_id'])
        for u in users:
            writer.writerow([
                u.name, u.first_name, u.last_name, u.email,
                u.member_role, u.points, u.member_created_at, u.last_active,
                u.community_slug, u.skool_id
            ])
        csv_data = output.getvalue()
        return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=members.csv'})

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
        profiles = Profile.get_list(
            "SELECT * FROM profile WHERE skool_id = ? ORDER BY fetched_at DESC LIMIT 1",
            [user.skool_id]
        )
        if not profiles:
            return jsonify([])
        profile = profiles[0]
        groups = json.loads(profile.groups_member_of) if profile.groups_member_of else []
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
        likes = Like.get_list(
            "SELECT DISTINCT post_skool_id FROM like WHERE user_skool_id = ?",
            [user.skool_id]
        )
        if not likes:
            return jsonify([])
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

    # === Post Routes ===

    @app.route('/api/post/latest')
    def get_posts_latest():
        """Get latest post per skool_id (deduplicated)."""
        posts = Post.get_list(
            """SELECT * FROM post WHERE id IN (
                SELECT MAX(id) FROM post GROUP BY skool_id
            ) ORDER BY id DESC"""
        )
        return jsonify([p.to_dict() for p in posts])

    @app.route('/api/post/by-users', methods=['POST'])
    def get_posts_by_users():
        """Get posts filtered by user skool_ids (deduplicated: latest per skool_id)."""
        skool_ids = request.json.get('skool_ids', [])
        if not skool_ids:
            return jsonify([])
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
        posts.sort(key=lambda p: p.id, reverse=True)
        return jsonify([p.to_dict() for p in posts])

    # === Community Routes ===

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
        profiles = Model.query("SELECT skool_id, groups_member_of FROM profile WHERE groups_member_of != ''")
        slug_users = {}
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
        communities = OtherCommunity.get_list("SELECT * FROM othercommunity", [])
        result = []
        for c in communities:
            data = c.to_dict()
            data['shared_user_count'] = len(slug_users.get(c.slug, set()))
            result.append(data)
        result.sort(key=lambda x: -x['shared_user_count'])
        return jsonify(result)

    @app.route('/api/communities/by-users', methods=['POST'])
    def get_communities_by_users():
        """Get OtherCommunities where selected users are members, with selection and global count."""
        skool_ids = request.json.get('skool_ids', [])
        if not skool_ids:
            return jsonify([])
        all_profiles = Model.query("SELECT skool_id, groups_member_of FROM profile WHERE groups_member_of != ''")
        global_slug_users = {}
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
        skool_ids_set = set(skool_ids)
        selection_counts = {}
        for slug, users in global_slug_users.items():
            count = len(users & skool_ids_set)
            if count > 0:
                selection_counts[slug] = count
        if not selection_counts:
            return jsonify([])
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
        result = []
        for c in communities:
            data = c.to_dict()
            data['selection_count'] = selection_counts.get(c.slug, 0)
            data['shared_user_count'] = len(global_slug_users.get(c.slug, set()))
            result.append(data)
        result.sort(key=lambda x: (-x['selection_count'], -x['shared_user_count']))
        return jsonify(result)

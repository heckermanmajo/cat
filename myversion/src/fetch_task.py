from typing import List
import time

from .config_entry import ConfigEntry
from .fetch import Fetch
from model import Model
from .post import Post
from .user import User


class FetchStaleInformation:
    """Stale-Zeiten in Stunden. Namen müssen mit fetch type übereinstimmen."""
    POSTS = 24
    MEMBERS = 24
    LEADERBOARD = 24
    PROFILE = 7 * 24   # singular, wie der fetch type
    COMMENTS = 7 * 24
    LIKES = 7 * 24

    # Harte Cutoffs: ignoriere ältere Daten komplett
    MAX_POST_AGE_DAYS = 90        # comments/likes nur für Posts < 3 Monate
    MAX_USER_INACTIVE_DAYS = 90   # profiles nur für User online < 3 Monate


class FetchTask(Model):
    """
    A list fetch task is sent to the fetching-plugin so it knows what
    to fetch from Skool. The Fetch tasks are generated on the fly.

    NOTE: Skool nennt die Posts-Seite intern "community", wir nennen
    den Fetch-Typ "posts" weil es klarer ist.
    """
    type: str = "posts"  # members, posts, comments, likes, profile
    communitySlug: str = ""  # always needed
    pageParam: int = 1  # might be ignored
    userSkoolHexId: str = ""  # for profile fetch
    userName: str = ""  # for profile fetch URL
    postSkoolHexId: str = ""  # for comments/likes fetch
    postName: str = ""  # for comments/likes fetch URL

    # =========================================================================
    # Hilfsfunktionen
    # =========================================================================

    @staticmethod
    def _stale_threshold(fetch_type: str) -> int:
        """Returns unix timestamp threshold - fetches older than this are stale."""
        hours = getattr(FetchStaleInformation, fetch_type.upper(), 24)
        return int(time.time()) - (hours * 3600)

    @staticmethod
    def _get_valid_fetch(fetch_type: str, slug: str, page: int = None,
                         user_id: str = None, post_id: str = None) -> Fetch | None:
        """Returns most recent valid (not stale) fetch or None."""
        threshold = FetchTask._stale_threshold(fetch_type)
        sql = "SELECT * FROM fetch WHERE type = ? AND community_slug = ? AND status = 'ok' AND created_at > ?"
        args = [fetch_type, slug, threshold]

        if page is not None:
            sql += " AND page_param = ?"
            args.append(page)
        if user_id is not None:
            sql += " AND user_skool_id = ?"
            args.append(user_id)
        if post_id is not None:
            sql += " AND post_skool_id = ?"
            args.append(post_id)

        sql += " ORDER BY created_at DESC LIMIT 1"
        rows = Fetch.get_list(sql, args)
        return rows[0] if rows else None

    @staticmethod
    def _has_valid_fetch(fetch_type: str, slug: str, **kwargs) -> bool:
        return FetchTask._get_valid_fetch(fetch_type, slug, **kwargs) is not None

    @staticmethod
    def _get_valid_fetch_ids(fetch_type: str, slug: str, id_column: str) -> set:
        """Lädt alle IDs mit gültigen Fetches in ein Set (bulk statt N+1)."""
        threshold = FetchTask._stale_threshold(fetch_type)
        rows = Fetch.get_list(
            f"SELECT {id_column} FROM fetch WHERE type = ? AND community_slug = ? AND status = 'ok' AND created_at > ?",
            [fetch_type, slug, threshold]
        )
        return {getattr(r, id_column) for r in rows}

    @staticmethod
    def _get_total_pages(fetch_type: str, slug: str) -> int:
        """Get total_pages from page=1 fetch."""
        f = FetchTask._get_valid_fetch(fetch_type, slug, page=1)
        return f.total_pages if f else 0

    # =========================================================================
    # Task Generierung
    # =========================================================================

    @classmethod
    def generateFetchTasks(cls) -> List["FetchTask"]:
        """
        Generate fetch tasks in 3 phases:
        Phase 1: members + posts + leaderboard (all pages)
        Phase 2: profiles, comments, likes (only after phase 1 complete)
        """
        currentCommunity = ConfigEntry.getByKey("current_community")
        if currentCommunity is None or currentCommunity.value.strip() == "":
            return []  # No community selected

        slug = currentCommunity.value.strip()

        # Phase 1a: Erste Seite members + posts + leaderboard (parallel)
        initial_tasks = []
        if not cls._has_valid_fetch('members', slug, page=1):
            initial_tasks.append(cls({"type": "members", "communitySlug": slug, "pageParam": 1}))
        if not cls._has_valid_fetch('posts', slug, page=1):
            initial_tasks.append(cls({"type": "posts", "communitySlug": slug, "pageParam": 1}))
        if not cls._has_valid_fetch('leaderboard', slug, page=1):
            initial_tasks.append(cls({"type": "leaderboard", "communitySlug": slug, "pageParam": 1}))
        if initial_tasks:
            return initial_tasks

        # Phase 1b: Restliche Seiten
        members_total = cls._get_total_pages('members', slug)
        posts_total = cls._get_total_pages('posts', slug)
        leaderboard_total = cls._get_total_pages('leaderboard', slug)

        missing_tasks = []
        for page in range(2, members_total + 1):
            if not cls._has_valid_fetch('members', slug, page=page):
                missing_tasks.append(cls({"type": "members", "communitySlug": slug, "pageParam": page}))

        for page in range(2, posts_total + 1):
            if not cls._has_valid_fetch('posts', slug, page=page):
                missing_tasks.append(cls({"type": "posts", "communitySlug": slug, "pageParam": page}))

        for page in range(2, leaderboard_total + 1):
            if not cls._has_valid_fetch('leaderboard', slug, page=page):
                missing_tasks.append(cls({"type": "leaderboard", "communitySlug": slug, "pageParam": page}))

        if missing_tasks:
            return missing_tasks

        # Phase 2: profiles, comments, likes
        tasks = []
        tasks.extend(cls._generate_profile_tasks(slug))
        tasks.extend(cls._generate_comment_tasks(slug))
        tasks.extend(cls._generate_likes_tasks(slug))
        return tasks

    @classmethod
    def _generate_profile_tasks(cls, slug: str) -> List["FetchTask"]:
        """Profile tasks für User die in den letzten 3 Monaten online waren."""
        tasks = []
        now = time.time()
        cutoff = now - (FetchStaleInformation.MAX_USER_INACTIVE_DAYS * 86400)
        valid_ids = cls._get_valid_fetch_ids('profile', slug, 'user_skool_id')

        users = User.get_list("SELECT * FROM user WHERE community_slug = ?", [slug])
        for u in users:
            # Skip wenn User zu lange inaktiv
            if u.last_active:
                try:
                    from datetime import datetime
                    last_active_ts = datetime.fromisoformat(u.last_active.replace('Z', '+00:00')).timestamp()
                    if last_active_ts < cutoff:
                        continue
                except:
                    pass

            if u.skool_id not in valid_ids:
                tasks.append(cls({
                    "type": "profile",
                    "communitySlug": slug,
                    "userSkoolHexId": u.skool_id,
                    "userName": u.name,
                }))
        return tasks

    @classmethod
    def _generate_comment_tasks(cls, slug: str) -> List["FetchTask"]:
        """Comment tasks für Posts < 3 Monate mit comments > 0."""
        tasks = []
        now = time.time()
        cutoff = now - (FetchStaleInformation.MAX_POST_AGE_DAYS * 86400)
        valid_ids = cls._get_valid_fetch_ids('comments', slug, 'post_skool_id')

        posts = Post.get_list(
            "SELECT * FROM post WHERE community_slug = ? AND COALESCE(comments, 0) > 0",
            [slug]
        )
        for p in posts:
            # Skip wenn Post zu alt
            if p.skool_created_at:
                try:
                    from datetime import datetime
                    created_ts = datetime.fromisoformat(p.skool_created_at.replace('Z', '+00:00')).timestamp()
                    if created_ts < cutoff:
                        continue
                except:
                    pass

            if p.skool_id not in valid_ids:
                tasks.append(cls({
                    "type": "comments",
                    "communitySlug": slug,
                    "postSkoolHexId": p.skool_id,
                    "postName": p.name,
                }))
        return tasks

    @classmethod
    def _generate_likes_tasks(cls, slug: str) -> List["FetchTask"]:
        """Likes tasks für toplevel Posts < 3 Monate mit upvotes > 0."""
        tasks = []
        now = time.time()
        cutoff = now - (FetchStaleInformation.MAX_POST_AGE_DAYS * 86400)
        valid_ids = cls._get_valid_fetch_ids('likes', slug, 'post_skool_id')

        posts = Post.get_list(
            "SELECT * FROM post WHERE community_slug = ? AND COALESCE(is_toplevel, 0) = 1 AND COALESCE(upvotes, 0) > 0",
            [slug]
        )
        for p in posts:
            # Skip wenn Post zu alt
            if p.skool_created_at:
                try:
                    from datetime import datetime
                    created_ts = datetime.fromisoformat(p.skool_created_at.replace('Z', '+00:00')).timestamp()
                    if created_ts < cutoff:
                        continue
                except:
                    pass

            if p.skool_id not in valid_ids:
                tasks.append(cls({
                    "type": "likes",
                    "communitySlug": slug,
                    "postSkoolHexId": p.skool_id,
                    "postName": p.name,
                }))
        return tasks

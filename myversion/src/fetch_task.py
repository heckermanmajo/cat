from typing import List
import time

from .config_entry import ConfigEntry
from .fetch import Fetch
from .other_community import OtherCommunity
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
    LIKES = 2 * 24     # default 2 days, configurable via settings
    COMMUNITY_ABOUT = 30 * 24  # About pages selten aktualisiert

    # Harte Cutoffs: ignoriere ältere Daten komplett (defaults, likes are configurable)
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
    groupSkoolId: str = ""  # Skool UUID for api2.skool.com calls (comments/likes)
    comment: str = ""  # explains why this task was generated

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
            initial_tasks.append(cls({"type": "members", "communitySlug": slug, "pageParam": 1,
                "comment": "Initial members fetch (page 1) to get total page count"}))
        if not cls._has_valid_fetch('posts', slug, page=1):
            initial_tasks.append(cls({"type": "posts", "communitySlug": slug, "pageParam": 1,
                "comment": "Initial posts fetch (page 1) to get total page count"}))
        if not cls._has_valid_fetch('leaderboard', slug, page=1):
            initial_tasks.append(cls({"type": "leaderboard", "communitySlug": slug, "pageParam": 1,
                "comment": "Initial leaderboard fetch (page 1) to get user points"}))
        if initial_tasks:
            return initial_tasks

        # Phase 1b: Restliche Seiten
        members_total = cls._get_total_pages('members', slug)
        posts_total = cls._get_total_pages('posts', slug)
        leaderboard_total = cls._get_total_pages('leaderboard', slug)

        missing_tasks = []
        for page in range(2, members_total + 1):
            if not cls._has_valid_fetch('members', slug, page=page):
                missing_tasks.append(cls({"type": "members", "communitySlug": slug, "pageParam": page,
                    "comment": f"Members page {page}/{members_total}"}))

        for page in range(2, posts_total + 1):
            if not cls._has_valid_fetch('posts', slug, page=page):
                missing_tasks.append(cls({"type": "posts", "communitySlug": slug, "pageParam": page,
                    "comment": f"Posts page {page}/{posts_total}"}))

        for page in range(2, leaderboard_total + 1):
            if not cls._has_valid_fetch('leaderboard', slug, page=page):
                missing_tasks.append(cls({"type": "leaderboard", "communitySlug": slug, "pageParam": page,
                    "comment": f"Leaderboard page {page}/{leaderboard_total}"}))

        if missing_tasks:
            return missing_tasks

        # Phase 2: profiles, comments, likes
        tasks = []
        tasks.extend(cls._generate_profile_tasks(slug))
        tasks.extend(cls._generate_comment_tasks(slug))
        tasks.extend(cls._generate_likes_tasks(slug))

        # Phase 3: community about pages for other communities above threshold
        tasks.extend(cls._generate_community_about_tasks())
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
                    "comment": f"Profile for user '{u.name}' (active in last 90 days)",
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
                    "groupSkoolId": p.group_id,  # Skool UUID for api2.skool.com
                    "comment": f"Comments for post '{p.name}' ({p.comments} comments, <90 days old)",
                }))
        return tasks

    @classmethod
    def _get_ever_fetched_ids(cls, fetch_type: str, slug: str, id_column: str) -> set:
        """Lädt alle IDs die jemals gefetched wurden (egal ob stale oder nicht)."""
        rows = Fetch.get_list(
            f"SELECT DISTINCT {id_column} FROM fetch WHERE type = ? AND community_slug = ? AND status = 'ok'",
            [fetch_type, slug]
        )
        return {getattr(r, id_column) for r in rows}

    @classmethod
    def _get_likes_settings(cls) -> dict:
        """Read likes settings from ConfigEntry with defaults."""
        settings = {
            'stale_days': 2,
            'initial_max_days': 90,
            'refetch_max_days': 7,
            'fetch_comments': False,
        }
        stale = ConfigEntry.getByKey('likes_stale_days')
        if stale and stale.value:
            try: settings['stale_days'] = int(stale.value)
            except: pass
        initial = ConfigEntry.getByKey('likes_initial_max_days')
        if initial and initial.value:
            try: settings['initial_max_days'] = int(initial.value)
            except: pass
        refetch = ConfigEntry.getByKey('likes_refetch_max_days')
        if refetch and refetch.value:
            try: settings['refetch_max_days'] = int(refetch.value)
            except: pass
        fetch_comments = ConfigEntry.getByKey('likes_fetch_comments')
        if fetch_comments and fetch_comments.value == 'true':
            settings['fetch_comments'] = True
        return settings

    @classmethod
    def _generate_likes_tasks(cls, slug: str) -> List["FetchTask"]:
        """
        Likes tasks für Posts mit upvotes > 0.
        - Initial fetch (noch nie gefetched): Posts < initial_max_days (default 90)
        - Re-fetch (stale): nur Posts < refetch_max_days (default 7)
        - By default only toplevel posts, comments optional via settings
        """
        tasks = []
        now = time.time()
        settings = cls._get_likes_settings()

        cutoff_initial = now - (settings['initial_max_days'] * 86400)
        cutoff_refetch = now - (settings['refetch_max_days'] * 86400)
        stale_threshold = int(now) - (settings['stale_days'] * 86400)

        # Use custom stale threshold for likes
        rows = Fetch.get_list(
            "SELECT post_skool_id FROM fetch WHERE type = ? AND community_slug = ? AND status = 'ok' AND created_at > ?",
            ['likes', slug, stale_threshold]
        )
        valid_ids = {r.post_skool_id for r in rows}
        ever_fetched_ids = cls._get_ever_fetched_ids('likes', slug, 'post_skool_id')

        # Build SQL based on whether comments should be fetched
        if settings['fetch_comments']:
            sql = "SELECT * FROM post WHERE community_slug = ? AND COALESCE(upvotes, 0) > 0"
        else:
            sql = "SELECT * FROM post WHERE community_slug = ? AND COALESCE(is_toplevel, 0) = 1 AND COALESCE(upvotes, 0) > 0"
        posts = Post.get_list(sql, [slug])

        for p in posts:
            # Skip wenn bereits gültiger Fetch existiert
            if p.skool_id in valid_ids:
                continue

            # Cutoff abhängig davon ob schon mal gefetched
            was_fetched_before = p.skool_id in ever_fetched_ids
            cutoff = cutoff_refetch if was_fetched_before else cutoff_initial

            # Skip wenn Post zu alt für den jeweiligen Cutoff
            if p.skool_created_at:
                try:
                    from datetime import datetime
                    created_ts = datetime.fromisoformat(p.skool_created_at.replace('Z', '+00:00')).timestamp()
                    if created_ts < cutoff:
                        continue
                except:
                    pass

            is_comment = not getattr(p, 'is_toplevel', False)
            post_type = "comment" if is_comment else "post"
            if was_fetched_before:
                comment = f"Re-fetch likes for {post_type} '{p.name}' ({p.upvotes} likes, <{settings['refetch_max_days']}d old)"
            else:
                comment = f"Initial likes fetch for {post_type} '{p.name}' ({p.upvotes} likes, <{settings['initial_max_days']}d old)"
            tasks.append(cls({
                "type": "likes",
                "communitySlug": slug,
                "postSkoolHexId": p.skool_id,
                "postName": p.name,
                "groupSkoolId": p.group_id,  # Skool UUID for api2.skool.com
                "comment": comment,
            }))
        return tasks

    @classmethod
    def _generate_community_about_tasks(cls) -> List["FetchTask"]:
        """
        Generate tasks to fetch about pages for other communities
        that have at least min_shared_members users.
        """
        import json
        from .profile import Profile
        tasks = []

        # Get min_shared_members threshold from settings (default 10)
        min_threshold_entry = ConfigEntry.getByKey('min_shared_members')
        min_threshold = 10
        if min_threshold_entry and min_threshold_entry.value:
            try:
                min_threshold = int(min_threshold_entry.value)
            except:
                pass

        # Calculate shared_user_count on-demand from profiles
        profiles = Profile.get_list("SELECT skool_id, groups_member_of FROM profile WHERE groups_member_of != ''", [])
        slug_users = {}  # slug -> set of skool_ids
        for p in profiles:
            groups = json.loads(p.groups_member_of) if p.groups_member_of else []
            if not groups:
                continue
            for g in groups:
                slug = g.get('name', '')
                if slug:
                    if slug not in slug_users:
                        slug_users[slug] = set()
                    slug_users[slug].add(p.skool_id)

        # Get communities that haven't been fetched recently
        threshold = cls._stale_threshold('community_about')
        communities = OtherCommunity.get_list(
            "SELECT * FROM othercommunity WHERE about_fetched = 0",
            []
        )

        for oc in communities:
            shared_count = len(slug_users.get(oc.slug, set()))
            if shared_count < min_threshold:
                continue

            # Check if we have a recent fetch for this community's about page
            recent_fetch = Fetch.get_list(
                "SELECT * FROM fetch WHERE type = 'community_about' AND community_slug = ? AND status = 'ok' AND created_at > ?",
                [oc.slug, threshold]
            )
            if not recent_fetch:
                tasks.append(cls({
                    "type": "community_about",
                    "communitySlug": oc.slug,
                    "comment": f"About page for '{oc.slug}' ({shared_count} shared members)",
                }))

        return tasks

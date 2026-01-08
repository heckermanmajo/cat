from typing import List

import utils
from .config_entry import ConfigEntry
from .model import Model
from .post import Post
from .user import User

class FetchTask(Model):
    """
    A list fetch task is sent to the fetching-plugin so it knows what
    to fetch from Skool. The Fetch tasks are generated on the fly.

    NOTE: Skool nennt die Posts-Seite intern "community", wir nennen
    den Fetch-Typ "posts" weil es klarer ist.
    """
    type: str = "posts" # members, posts, comments, likes, profile
    communitySlug: str = "" # always needed
    pageParam: int = 1 # might be ignored
    userSkoolHexId: str = "" # for profile fetch
    userName: str = "" # for profile fetch URL
    postSkoolHexId: str = "" # for comments/likes fetch
    postName: str = "" # for comments/likes fetch URL

    @classmethod
    def generateFetchTasks(cls) -> List["FetchTask"]:
        """
        Generate a list of fetch tasks to be processed by the fetching-plugin.
        """
        currentCommunity = ConfigEntry.getByKey("data.current_community")
        if currentCommunity is None or currentCommunity.value.strip() == "":
            utils.err("Fetching tasks need a current community")

        slug = "hoomans"  # TODO: use currentCommunity.value
        tasks = [
            cls({"type": "members", "communitySlug": slug, "pageParam": 1}),
            cls({"type": "posts", "communitySlug": slug, "pageParam": 1}),
        ]

        # Comments tasks: für jeden Post mit comments > 0
        posts_with_comments = Post.get_list(
            "SELECT * FROM post WHERE community_slug = ? AND COALESCE(comments, 0) > 0",
            [slug]
        )
        for p in posts_with_comments:
            tasks.append(cls({
                "type": "comments",
                "communitySlug": slug,
                "postSkoolHexId": p.skool_id,
                "postName": p.name,  # slug für URL
            }))

        # Likes tasks: für jeden toplevel Post mit upvotes > 0
        toplevel_with_likes = Post.get_list(
            "SELECT * FROM post WHERE community_slug = ? AND COALESCE(is_toplevel, 0) = 1 AND COALESCE(upvotes, 0) > 0",
            [slug]
        )
        for p in toplevel_with_likes:
            tasks.append(cls({
                "type": "likes",
                "communitySlug": slug,
                "postSkoolHexId": p.skool_id,
                "postName": p.name,  # slug für URL
            }))

        # Profile tasks: für jeden User
        users = User.get_list(
            "SELECT * FROM user WHERE community_slug = ?",
            [slug]
        )
        for u in users:
            tasks.append(cls({
                "type": "profile",
                "communitySlug": slug,
                "userSkoolHexId": u.skool_id,
                "userName": u.name,  # username für URL
            }))

        return tasks
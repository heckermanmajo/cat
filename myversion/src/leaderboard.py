from model import Model


class Leaderboard(Model):
    """
    Extrahiert aus leaderboardsData in community/posts-Fetches.
    Speichert rank und points pro User pro Community.
    """
    fetch_id: int = 0
    fetched_at: int = 0
    community_slug: str = ""
    user_skool_id: str = ""
    rank: int = 0
    points: int = 0

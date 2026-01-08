from .model import Model

class Fetch(Model):
    """
    Rohdaten vom Plugin. Jeder Fetch ist ein API-Response von Skool.
    Später extrahieren wir daraus Members, Posts, etc.
    """
    type: str = ""  # members, posts, comments, likes, profile
    community_slug: str = ""
    page_param: int = 1
    user_skool_id: str = ""   # für profile fetch
    post_skool_id: str = ""   # für comments/likes fetch
    raw_data: str = ""  # JSON string der Skool-Response
    status: str = "ok"  # ok, error
    error_message: str = ""

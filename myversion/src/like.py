from model import Model


class Like(Model):
    """
    Extrahiert aus likes-Fetches (api2.skool.com/posts/{id}/vote-users).
    Speichert welcher User welchen Post geliked hat.
    """
    fetch_id: int = 0           # Link zur Quelle (Fetch.id)
    fetched_at: int = 0         # Zeitpunkt der Extraktion
    community_slug: str = ""    # Aus welcher Community

    # Relation
    post_skool_id: str = ""     # Der gelikete Post
    user_skool_id: str = ""     # Der User der geliked hat

    # User-Daten (für schnellen Zugriff, ohne Join)
    user_name: str = ""
    user_first_name: str = ""
    user_last_name: str = ""

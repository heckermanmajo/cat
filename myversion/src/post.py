from .model import Model

class Post(Model):
    """
    Extrahiert aus posts-Fetches (Skool nennt es "community").
    Pro Fetch wird eine Instanz erstellt -> Verlauf über Zeit möglich.
    """
    fetch_id: int = 0           # Link zur Quelle (Fetch.id)
    fetched_at: int = 0         # Zeitpunkt der Extraktion
    community_slug: str = ""    # Aus welcher Community

    # Skool Post Felder (1:1 Namen)
    skool_id: str = ""          # post.id von Skool
    name: str = ""              # slug
    post_type: str = ""
    group_id: str = ""
    user_id: str = ""
    label_id: str = ""
    root_id: str = ""
    skool_created_at: str = ""
    skool_updated_at: str = ""
    metadata: str = ""          # JSON string (title, content, upvotes, etc.)

    # Eingebettete User-Daten (für schnellen Zugriff)
    user_name: str = ""
    user_metadata: str = ""     # JSON string

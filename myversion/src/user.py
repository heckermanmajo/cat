from .model import Model

class User(Model):
    """
    Extrahiert aus members-Fetches. Skool-Felder 1:1 übernommen.
    Pro Fetch wird eine Instanz erstellt -> Verlauf über Zeit möglich.
    """
    fetch_id: int = 0           # Link zur Quelle (Fetch.id)
    fetched_at: int = 0         # Zeitpunkt der Extraktion
    community_slug: str = ""    # Aus welcher Community

    # Skool User Felder (1:1 Namen)
    skool_id: str = ""          # user.id von Skool
    name: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    skool_created_at: str = ""
    skool_updated_at: str = ""
    metadata: str = ""          # JSON string (bio, picture, etc.)

    # Skool Member Felder (Membership in dieser Community)
    member_id: str = ""
    member_role: str = ""
    member_group_id: str = ""
    member_created_at: str = ""
    member_metadata: str = ""   # JSON string

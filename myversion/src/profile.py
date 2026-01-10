from model import Model

class Profile(Model):
    """
    Extrahiert aus profile-Fetches. Enthält mehr Daten als User (aus members).
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
    metadata: str = ""          # JSON string (bio, links, picture, etc.)

    # Profile-spezifische Daten (aus profileData)
    total_posts: int = 0
    total_followers: int = 0
    total_following: int = 0
    total_contributions: int = 0
    total_groups: int = 0

    # Member-Daten in dieser Community
    member_id: str = ""
    member_role: str = ""
    member_metadata: str = ""   # JSON string

    # Gruppen-Listen (JSON strings)
    groups_member_of: str = ""      # JSON array
    groups_created_by_user: str = ""  # JSON array
    daily_activities: str = ""      # JSON object

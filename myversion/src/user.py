from model import Model
from src.config_entry import ConfigEntry
from src.members_filter import MembersFilter


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
    member_created_at: int = 0  # Unix timestamp (converted from ISO)
    member_metadata: str = ""   # JSON string

    # Extrahierte Felder aus metadata
    picture_url: str = ""       # Profilbild-URL
    bio: str = ""               # Bio-Text

    # Leaderboard-Daten (aus separatem Leaderboard-Fetch)
    points: int = 0                  # Gamification-Punkte aus Leaderboard
    leaderboard_applied_at: int = 0  # Wann points zuletzt aktualisiert

    # Activity
    last_active: int = 0        # Unix timestamp from metadata.lastOffline
    is_online: int = 0          # 1 = currently online

    @classmethod
    def all(cls, order: str = 'id DESC') -> list['User']:
        """
        SELECT *
            FROM (
                SELECT
                    us.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY platform_user_id
                        ORDER BY created_at DESC
                    ) AS rn
                FROM user_snapshots us
            )
            WHERE rn = 1;

        """
        communitySlug = ConfigEntry.getByKey('current_community')
        return cls.filtered(MembersFilter({'communitySlug': communitySlug.value}))

    @classmethod
    def filtered(cls, f: MembersFilter) -> list['User']:
        """
        Returns deduplicated users (latest snapshot per skool_id) with filters applied.
        """
        filter_sql, filter_args = f.to_sql()

        # Extract WHERE and ORDER BY from filter SQL
        # filter_sql = "SELECT * FROM user WHERE 1=1 AND ... ORDER BY ..."
        where_start = filter_sql.find('WHERE')
        order_start = filter_sql.find('ORDER BY')

        where_clause = filter_sql[where_start + 6:order_start].strip() if order_start > 0 else filter_sql[where_start + 6:].strip()
        order_clause = filter_sql[order_start + 9:].strip() if order_start > 0 else 'name ASC'

        sql = f"""
            SELECT * FROM (
                SELECT
                    us.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY community_slug, skool_id
                        ORDER BY created_at DESC
                    ) AS rn
                FROM {cls.__name__.lower()} us
                WHERE {where_clause}
            )
            WHERE rn = 1
            ORDER BY {order_clause}
        """
        return cls.get_list(sql, filter_args)

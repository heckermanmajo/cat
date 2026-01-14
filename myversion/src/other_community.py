from model import Model


class OtherCommunity(Model):
    """
    Communities discovered from user profiles.
    Only the slug/name is known until we fetch the about page.
    Note: shared_user_count is calculated on-demand from profiles, not stored.
    """
    slug: str = ""              # Community slug (URL identifier)
    name: str = ""              # Community name (if known)
    about_fetched: int = 0      # 1 if about page was fetched
    about_data: str = ""        # JSON string with about page data

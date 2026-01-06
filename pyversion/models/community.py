"""
Community Dataclass - Repräsentiert eine Skool-Community
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import json

from .base import get_nested


@dataclass
class Community:
    """Eine Skool-Community"""

    id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    member_count: int = 0
    post_count: int = 0
    picture: Optional[str] = None
    raw_fetch_id: Optional[int] = None
    extracted_at: Optional[datetime] = None

    @classmethod
    def extract_from_about_page(
        cls,
        raw_json: str,
        entity_id: str,
        raw_fetch_id: int
    ) -> Optional["Community"]:
        """
        Extrahiert Community aus einem about_page raw_fetch.

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json (entity_type='about_page')
            entity_id: Die entity_id aus raw_fetches (wird als ID verwendet)
            raw_fetch_id: ID des raw_fetches-Eintrags

        Returns:
            Community-Objekt oder None
        """
        # Community-ID ist immer der Slug aus entity_id (ohne _page_X)
        community_slug = entity_id.split('_page_')[0] if '_page_' in entity_id else entity_id

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})
            group = page_props.get('group') or {}
            meta = group.get('metadata') or {}

            return cls(
                id=community_slug,  # Slug als ID für Konsistenz
                name=meta.get('name', group.get('name', '')) or community_slug,
                slug=community_slug,
                description=meta.get('description', ''),
                member_count=meta.get('members', 0),
                post_count=meta.get('posts', 0),
                picture=meta.get('picture', ''),
                raw_fetch_id=raw_fetch_id,
                extracted_at=datetime.now()
            )

        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    @classmethod
    def extract_from_community_page(
        cls,
        raw_json: str,
        entity_id: str,
        raw_fetch_id: int
    ) -> Optional["Community"]:
        """
        Extrahiert Community-Basis-Infos aus einem community_page raw_fetch.
        (Weniger vollständig als about_page, aber enthält group-Infos)

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json (entity_type='community_page')
            entity_id: Die entity_id aus raw_fetches (wird als ID verwendet)
            raw_fetch_id: ID des raw_fetches-Eintrags

        Returns:
            Community-Objekt oder None
        """
        # Community-ID ist immer der Slug aus entity_id (ohne _page_X)
        community_slug = entity_id.split('_page_')[0] if '_page_' in entity_id else entity_id

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})
            group = page_props.get('group') or {}
            meta = group.get('metadata') or {}

            # Post-Count aus postTrees zählen
            post_trees = page_props.get('postTrees', [])
            post_count = len(post_trees)

            return cls(
                id=community_slug,  # Slug als ID für Konsistenz
                name=meta.get('name', group.get('name', '')) or community_slug,
                slug=community_slug,
                description=meta.get('description', ''),
                member_count=meta.get('members', 0),
                post_count=post_count,
                picture=meta.get('picture', ''),
                raw_fetch_id=raw_fetch_id,
                extracted_at=datetime.now()
            )

        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    @classmethod
    def extract_from_members_page(
        cls,
        raw_json: str,
        entity_id: str,
        raw_fetch_id: int
    ) -> Optional["Community"]:
        """
        Extrahiert Community-Infos aus einem members raw_fetch.

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json (entity_type='members')
            entity_id: Die entity_id aus raw_fetches (wird als ID verwendet)
            raw_fetch_id: ID des raw_fetches-Eintrags

        Returns:
            Community-Objekt oder None
        """
        # Community-ID ist immer der Slug aus entity_id (ohne _page_X)
        community_slug = entity_id.split('_page_')[0] if '_page_' in entity_id else entity_id

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})
            group = page_props.get('group') or {}
            meta = group.get('metadata') or {}

            return cls(
                id=community_slug,  # Slug als ID für Konsistenz
                name=meta.get('name', group.get('name', '')) or community_slug,
                slug=community_slug,
                description=meta.get('description', ''),
                member_count=meta.get('members', 0),
                post_count=meta.get('posts', 0),
                picture=meta.get('picture', ''),
                raw_fetch_id=raw_fetch_id,
                extracted_at=datetime.now()
            )

        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def to_db_row(self) -> dict:
        """Konvertiert zu Dictionary für DB-Insert"""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'member_count': self.member_count,
            'post_count': self.post_count,
            'picture': self.picture,
            'raw_fetch_id': self.raw_fetch_id,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "Community":
        """Erstellt Community aus DB-Row (dict)"""
        return cls(
            id=row['id'],
            name=row['name'],
            slug=row.get('slug'),
            description=row.get('description'),
            member_count=row.get('member_count', 0),
            post_count=row.get('post_count', 0),
            picture=row.get('picture'),
            raw_fetch_id=row.get('raw_fetch_id'),
            extracted_at=datetime.fromisoformat(row['extracted_at']) if row.get('extracted_at') else None
        )

    @staticmethod
    def upsert_sql() -> str:
        """SQL für INSERT OR REPLACE"""
        return """
            INSERT OR REPLACE INTO communities (
                id, name, slug, description, member_count, post_count,
                picture, raw_fetch_id, extracted_at
            ) VALUES (
                :id, :name, :slug, :description, :member_count, :post_count,
                :picture, :raw_fetch_id, :extracted_at
            )
        """

    def merge_with(self, other: "Community") -> "Community":
        """
        Merged zwei Community-Objekte (nimmt bessere/vollständigere Werte).
        Nützlich wenn Daten aus verschiedenen Quellen kommen.
        """
        return Community(
            id=self.id,
            name=self.name or other.name,
            slug=self.slug or other.slug,
            description=self.description or other.description,
            member_count=max(self.member_count, other.member_count),
            post_count=max(self.post_count, other.post_count),
            picture=self.picture or other.picture,
            raw_fetch_id=self.raw_fetch_id or other.raw_fetch_id,
            extracted_at=max(self.extracted_at, other.extracted_at) if self.extracted_at and other.extracted_at else (self.extracted_at or other.extracted_at)
        )

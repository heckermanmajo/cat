"""
Member Dataclass - Repräsentiert ein Mitglied einer Skool-Community
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json

from .base import get_nested


@dataclass
class Member:
    """Ein Mitglied einer Skool-Community"""

    id: str
    name: str
    community_id: str
    slug: Optional[str] = None
    picture: Optional[str] = None
    role: str = "member"  # admin, group-moderator, member, owner
    is_owner: bool = False
    joined_at: Optional[str] = None
    last_online: Optional[str] = None
    post_count: int = 0
    level: int = 0
    raw_fetch_id: Optional[int] = None
    extracted_at: Optional[datetime] = None

    @classmethod
    def extract_from_raw_json(
        cls,
        raw_json: str,
        raw_fetch_id: int,
        entity_id: str = ''
    ) -> List["Member"]:
        """
        Extrahiert alle Members aus einem raw_fetches-Eintrag (entity_type='members').

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json
            raw_fetch_id: ID des raw_fetches-Eintrags
            entity_id: Die entity_id aus raw_fetches (Fallback für community_id)

        Returns:
            Liste von Member-Objekten
        """
        members = []

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})
            group = page_props.get('group') or {}
            # Primär: group.id, Fallback: Slug aus entity_id (ohne _page_X)
            community_id = group.get('id', '')
            if not community_id and entity_id:
                community_id = entity_id.split('_page_')[0] if '_page_' in entity_id else entity_id
            owner_id = get_nested(group, 'metadata', 'owner', default='')

            for user in page_props.get('users', []):
                user_id = user.get('id')
                if not user_id:
                    continue

                meta = user.get('metadata', {})
                member_data = user.get('member', {})
                member_meta = member_data.get('metadata', {})

                # Name: firstName + lastName, Fallback auf metadata.name
                first_name = user.get('firstName', '')
                last_name = user.get('lastName', '')
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = meta.get('name', user.get('name', ''))

                # Role und Level aus metadata.spData extrahieren
                role = 'member'
                level = 0
                sp_data_str = meta.get('spData', '')
                if sp_data_str:
                    try:
                        sp = json.loads(sp_data_str)
                        # role: 0=member, 1=admin, 2=owner, 3=group-moderator
                        role_num = sp.get('role', 0)
                        role_map = {0: 'member', 1: 'admin', 2: 'owner', 3: 'group-moderator'}
                        role = role_map.get(role_num, 'member')
                        level = sp.get('lv', 0)
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Picture: pictureProfile oder pictureBubble
                picture = meta.get('pictureProfile', '') or meta.get('pictureBubble', '')

                # Post count aus member.metadata
                member_meta = member_data.get('metadata', {})
                post_count = member_meta.get('numGenericPosts', 0) if member_meta else 0

                member = cls(
                    id=user_id,
                    name=full_name,
                    community_id=community_id,
                    slug=user.get('name', ''),  # In Skool ist 'name' der Slug
                    picture=picture,
                    role=role,
                    is_owner=(user_id == owner_id),
                    joined_at=member_data.get('createdAt'),  # joinedAt ist createdAt
                    last_online=str(meta.get('lastOffline', '')) if meta.get('lastOffline') else None,
                    post_count=post_count,
                    level=level,
                    raw_fetch_id=raw_fetch_id,
                    extracted_at=datetime.now()
                )
                members.append(member)

        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        return members

    def to_db_row(self) -> dict:
        """Konvertiert zu Dictionary für DB-Insert"""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'picture': self.picture,
            'community_id': self.community_id,
            'role': self.role,
            'is_owner': 1 if self.is_owner else 0,
            'joined_at': self.joined_at,
            'last_online': self.last_online,
            'post_count': self.post_count,
            'level': self.level,
            'raw_fetch_id': self.raw_fetch_id,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "Member":
        """Erstellt Member aus DB-Row (dict)"""
        return cls(
            id=row['id'],
            name=row['name'],
            community_id=row['community_id'],
            slug=row.get('slug'),
            picture=row.get('picture'),
            role=row.get('role', 'member'),
            is_owner=bool(row.get('is_owner', 0)),
            joined_at=row.get('joined_at'),
            last_online=row.get('last_online'),
            post_count=row.get('post_count', 0),
            level=row.get('level', 0),
            raw_fetch_id=row.get('raw_fetch_id'),
            extracted_at=datetime.fromisoformat(row['extracted_at']) if row.get('extracted_at') else None
        )

    @staticmethod
    def upsert_sql() -> str:
        """SQL für INSERT OR REPLACE"""
        return """
            INSERT OR REPLACE INTO members (
                id, name, slug, picture, community_id, role, is_owner,
                joined_at, last_online, post_count, level, raw_fetch_id, extracted_at
            ) VALUES (
                :id, :name, :slug, :picture, :community_id, :role, :is_owner,
                :joined_at, :last_online, :post_count, :level, :raw_fetch_id, :extracted_at
            )
        """

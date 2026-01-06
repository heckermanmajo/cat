"""
Post Dataclass - Repräsentiert einen Beitrag in einer Skool-Community
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import json

from .base import get_nested


@dataclass
class Post:
    """Ein Beitrag in einer Skool-Community"""

    id: str
    community_id: str
    title: Optional[str] = None
    content: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    likes: int = 0
    comments: int = 0
    created_at: Optional[str] = None
    raw_fetch_id: Optional[int] = None
    extracted_at: Optional[datetime] = None

    @classmethod
    def extract_from_community_page(
        cls,
        raw_json: str,
        raw_fetch_id: int,
        entity_id: str = ''
    ) -> List["Post"]:
        """
        Extrahiert Posts aus einem community_page raw_fetch.

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json (entity_type='community_page')
            raw_fetch_id: ID des raw_fetches-Eintrags
            entity_id: Die entity_id aus raw_fetches (für community_id)

        Returns:
            Liste von Post-Objekten
        """
        posts = []

        # Community-ID aus entity_id ableiten (Slug ohne _page_X)
        community_slug = entity_id.split('_page_')[0] if '_page_' in entity_id else entity_id

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})

            for pt in page_props.get('postTrees', []):
                post_data = pt.get('post', {})
                post_id = post_data.get('id')
                if not post_id:
                    continue

                meta = post_data.get('metadata', {})
                user = post_data.get('user', {})

                # Author-Name zusammensetzen
                first_name = user.get('firstName', '')
                last_name = user.get('lastName', '')
                author_name = f"{first_name} {last_name}".strip()

                post = cls(
                    id=post_id,
                    community_id=community_slug or post_data.get('groupId', ''),
                    title=meta.get('title', ''),
                    content=meta.get('content', ''),
                    author_id=post_data.get('userId', ''),
                    author_name=author_name or None,
                    likes=meta.get('upvotes', 0),
                    comments=meta.get('comments', 0),
                    created_at=post_data.get('createdAt'),
                    raw_fetch_id=raw_fetch_id,
                    extracted_at=datetime.now()
                )
                posts.append(post)

        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        return posts

    @classmethod
    def extract_from_post_details(
        cls,
        raw_json: str,
        raw_fetch_id: int,
        entity_id: str = ''
    ) -> Optional["Post"]:
        """
        Extrahiert einen Post aus post_details raw_fetch.

        Args:
            raw_json: JSON-String aus raw_fetches.raw_json (entity_type='post_details')
            raw_fetch_id: ID des raw_fetches-Eintrags
            entity_id: Die entity_id aus raw_fetches (für community_id)

        Returns:
            Post-Objekt oder None
        """
        # Community-Slug aus entity_id extrahieren (Format: community_postid)
        community_slug = entity_id.split('_')[0] if entity_id and '_' in entity_id else ''

        try:
            data = json.loads(raw_json)
            page_props = data.get('pageProps', {})
            post_tree = page_props.get('postTree', {})
            post_data = post_tree.get('post', {})

            post_id = post_data.get('id')
            if not post_id:
                return None

            meta = post_data.get('metadata', {})
            user = post_data.get('user', {})

            first_name = user.get('firstName', '')
            last_name = user.get('lastName', '')
            author_name = f"{first_name} {last_name}".strip()

            return cls(
                id=post_id,
                community_id=community_slug or post_data.get('groupId', ''),
                title=meta.get('title', ''),
                content=meta.get('content', ''),
                author_id=post_data.get('userId', ''),
                author_name=author_name or None,
                likes=meta.get('upvotes', 0),
                comments=meta.get('comments', 0),
                created_at=post_data.get('createdAt'),
                raw_fetch_id=raw_fetch_id,
                extracted_at=datetime.now()
            )

        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def to_db_row(self) -> dict:
        """Konvertiert zu Dictionary für DB-Insert"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'community_id': self.community_id,
            'likes': self.likes,
            'comments': self.comments,
            'created_at': self.created_at,
            'raw_fetch_id': self.raw_fetch_id,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "Post":
        """Erstellt Post aus DB-Row (dict)"""
        return cls(
            id=row['id'],
            community_id=row['community_id'],
            title=row.get('title'),
            content=row.get('content'),
            author_id=row.get('author_id'),
            author_name=row.get('author_name'),
            likes=row.get('likes', 0),
            comments=row.get('comments', 0),
            created_at=row.get('created_at'),
            raw_fetch_id=row.get('raw_fetch_id'),
            extracted_at=datetime.fromisoformat(row['extracted_at']) if row.get('extracted_at') else None
        )

    @staticmethod
    def upsert_sql() -> str:
        """SQL für INSERT OR REPLACE"""
        return """
            INSERT OR REPLACE INTO posts (
                id, title, content, author_id, author_name, community_id,
                likes, comments, created_at, raw_fetch_id, extracted_at
            ) VALUES (
                :id, :title, :content, :author_id, :author_name, :community_id,
                :likes, :comments, :created_at, :raw_fetch_id, :extracted_at
            )
        """

"""
Synthetic test data generator.
Creates realistic test data for API testing.
"""
import time
import json
import random
from typing import List, Dict

# Constants
DAY_SECONDS = 86400
NOW = int(time.time())

# Test communities
COMMUNITIES = ['test-community-alpha', 'test-community-beta', 'test-community-gamma']

# Roles distribution
ROLES = ['admin', 'moderator', 'member', 'member', 'member', 'member', 'member', 'member']

# Names for generating users
FIRST_NAMES = [
    'Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry',
    'Ivy', 'Jack', 'Karen', 'Leo', 'Mia', 'Nathan', 'Olivia', 'Peter',
    'Quinn', 'Rachel', 'Sam', 'Tina', 'Uma', 'Victor', 'Wendy', 'Xavier',
    'Yara', 'Zack', 'Anna', 'Ben', 'Clara', 'David', 'Emma', 'Felix'
]

LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Martin'
]


def generate_skool_id() -> str:
    """Generate a realistic Skool ID."""
    return f"usr_{random.randint(100000, 999999)}"


def generate_user(
    index: int,
    community_slug: str,
    fetch_id: int = 1,
    role: str = None,
    points: int = None,
    last_active_days_ago: int = None,
    joined_days_ago: int = None,
    is_online: bool = False,
    skool_id: str = None
) -> Dict:
    """Generate a single user with customizable attributes."""
    first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
    last_name = LAST_NAMES[index % len(LAST_NAMES)]
    name = f"{first_name.lower()}{last_name.lower()}{index}"

    if role is None:
        role = random.choice(ROLES)
    if points is None:
        points = random.randint(0, 5000)
    if last_active_days_ago is None:
        last_active_days_ago = random.randint(0, 180)
    if joined_days_ago is None:
        joined_days_ago = random.randint(30, 365)
    if skool_id is None:
        skool_id = generate_skool_id()

    return {
        'fetch_id': fetch_id,
        'fetched_at': NOW,
        'community_slug': community_slug,
        'skool_id': skool_id,
        'name': name,
        'email': f"{name}@test.example.com",
        'first_name': first_name,
        'last_name': last_name,
        'skool_created_at': '',
        'skool_updated_at': '',
        'metadata': json.dumps({'bio': f'Test user {index}'}),
        'member_id': f"mem_{random.randint(100000, 999999)}",
        'member_role': role,
        'member_group_id': '',
        'member_created_at': NOW - (joined_days_ago * DAY_SECONDS),
        'member_metadata': '{}',
        'picture_url': '',
        'bio': f'Test user {index}',
        'points': points,
        'leaderboard_applied_at': NOW,
        'last_active': NOW - (last_active_days_ago * DAY_SECONDS),
        'is_online': 1 if is_online else 0
    }


def generate_users(
    count: int,
    community_slug: str = 'test-community-alpha',
    fetch_id: int = 1
) -> List[Dict]:
    """Generate multiple users with varied attributes."""
    users = []
    for i in range(count):
        users.append(generate_user(i, community_slug, fetch_id))
    return users


def generate_post(
    index: int,
    community_slug: str,
    user_skool_id: str,
    user_name: str,
    fetch_id: int = 1,
    upvotes: int = None,
    comments: int = None,
    created_days_ago: int = None
) -> Dict:
    """Generate a single post."""
    if upvotes is None:
        upvotes = random.randint(0, 100)
    if comments is None:
        comments = random.randint(0, 50)
    if created_days_ago is None:
        created_days_ago = random.randint(0, 90)

    return {
        'fetch_id': fetch_id,
        'fetched_at': NOW,
        'community_slug': community_slug,
        'skool_id': f"post_{random.randint(100000, 999999)}",
        'name': f"test-post-{index}",
        'post_type': 'post',
        'group_id': '',
        'user_id': user_skool_id,
        'label_id': '',
        'root_id': '',
        'skool_created_at': str(NOW - (created_days_ago * DAY_SECONDS)),
        'skool_updated_at': '',
        'metadata': json.dumps({
            'title': f'Test Post {index}',
            'content': f'This is test content for post {index}.'
        }),
        'is_toplevel': 1,
        'comments': comments,
        'upvotes': upvotes,
        'user_name': user_name,
        'user_metadata': '{}'
    }


def generate_fetch(
    fetch_type: str,
    community_slug: str,
    page: int = 1
) -> Dict:
    """Generate a fetch record."""
    return {
        'type': fetch_type,
        'community_slug': community_slug,
        'page_param': page,
        'user_skool_id': '',
        'post_skool_id': '',
        'raw_data': '{}',
        'status': 'ok',
        'error_message': '',
        'total_items': 100,
        'total_pages': 1
    }


def generate_like(
    post_skool_id: str,
    user_skool_id: str,
    user_name: str,
    community_slug: str,
    fetch_id: int = 1
) -> Dict:
    """Generate a like record."""
    return {
        'fetch_id': fetch_id,
        'fetched_at': NOW,
        'community_slug': community_slug,
        'post_skool_id': post_skool_id,
        'user_skool_id': user_skool_id,
        'user_name': user_name,
        'user_first_name': '',
        'user_last_name': ''
    }


def generate_profile(
    user: Dict,
    communities: List[str] = None,
    fetch_id: int = 1
) -> Dict:
    """Generate a profile from a user with additional data."""
    if communities is None:
        communities = [user['community_slug']]

    groups_member_of = [
        {'name': slug, 'metadata': {'displayName': slug.replace('-', ' ').title()}}
        for slug in communities
    ]

    return {
        'fetch_id': fetch_id,
        'fetched_at': NOW,
        'community_slug': user['community_slug'],
        'skool_id': user['skool_id'],
        'name': user['name'],
        'email': user['email'],
        'first_name': user['first_name'],
        'last_name': user['last_name'],
        'skool_created_at': user['skool_created_at'],
        'skool_updated_at': user['skool_updated_at'],
        'metadata': user['metadata'],
        'total_posts': random.randint(0, 50),
        'total_followers': random.randint(0, 200),
        'total_following': random.randint(0, 100),
        'total_contributions': random.randint(0, 500),
        'total_groups': len(communities),
        'member_id': user['member_id'],
        'member_role': user['member_role'],
        'member_metadata': user['member_metadata'],
        'groups_member_of': json.dumps(groups_member_of),
        'groups_created_by_user': '[]',
        'daily_activities': '{}'
    }


class DataBuilder:
    """Builder for creating complex test scenarios."""

    def __init__(self, api):
        self.api = api
        self.users = []
        self.posts = []
        self.likes = []
        self.profiles = []
        self.fetches = []
        self.community = 'test-community-alpha'

    def with_community(self, slug: str) -> 'DataBuilder':
        """Set the community for subsequent operations."""
        self.community = slug
        return self

    def with_fetch(self, fetch_type: str = 'members') -> 'DataBuilder':
        """Add a fetch record."""
        self.fetches.append(generate_fetch(fetch_type, self.community))
        return self

    def with_users(self, count: int, **kwargs) -> 'DataBuilder':
        """Add users with optional customization."""
        fetch_id = len(self.fetches) if self.fetches else 1
        for i in range(count):
            user_kwargs = {k: v for k, v in kwargs.items()}
            self.users.append(generate_user(
                len(self.users),
                self.community,
                fetch_id,
                **user_kwargs
            ))
        return self

    def with_specific_user(self, **kwargs) -> 'DataBuilder':
        """Add a single user with specific attributes."""
        fetch_id = len(self.fetches) if self.fetches else 1
        self.users.append(generate_user(
            len(self.users),
            self.community,
            fetch_id,
            **kwargs
        ))
        return self

    def build(self) -> 'DataBuilder':
        """Insert all data into the database via API."""
        if self.fetches:
            self.api.bulk_fetches(self.fetches)
        if self.users:
            self.api.bulk_users(self.users)
        if self.posts:
            self.api.bulk_posts(self.posts)
        if self.likes:
            self.api.bulk_likes(self.likes)
        if self.profiles:
            self.api.bulk_profiles(self.profiles)

        # Set the community
        self.api.set_community(self.community)

        return self

    def get_users(self) -> List[Dict]:
        """Get the generated users."""
        return self.users


def setup_standard_test_data(api) -> DataBuilder:
    """
    Create a standard test dataset:
    - 100 users across 1 community
    - Various roles, points, activity levels
    """
    builder = DataBuilder(api)
    builder.with_community('test-community-alpha')
    builder.with_fetch('members')

    # 3 admins
    for i in range(3):
        builder.with_specific_user(
            role='admin',
            points=random.randint(3000, 5000),
            last_active_days_ago=random.randint(0, 7),
            joined_days_ago=random.randint(180, 365)
        )

    # 7 moderators
    for i in range(7):
        builder.with_specific_user(
            role='moderator',
            points=random.randint(1500, 3500),
            last_active_days_ago=random.randint(0, 30),
            joined_days_ago=random.randint(90, 270)
        )

    # 30 active members (last 7 days)
    for i in range(30):
        builder.with_specific_user(
            role='member',
            points=random.randint(100, 2000),
            last_active_days_ago=random.randint(0, 7),
            joined_days_ago=random.randint(30, 180)
        )

    # 30 semi-active members (last 30 days)
    for i in range(30):
        builder.with_specific_user(
            role='member',
            points=random.randint(50, 1000),
            last_active_days_ago=random.randint(8, 30),
            joined_days_ago=random.randint(60, 240)
        )

    # 20 inactive members (30+ days)
    for i in range(20):
        builder.with_specific_user(
            role='member',
            points=random.randint(0, 500),
            last_active_days_ago=random.randint(31, 180),
            joined_days_ago=random.randint(90, 365)
        )

    # 10 new members (joined in last 30 days)
    for i in range(10):
        builder.with_specific_user(
            role='member',
            points=random.randint(0, 200),
            last_active_days_ago=random.randint(0, 30),
            joined_days_ago=random.randint(1, 30)
        )

    return builder.build()

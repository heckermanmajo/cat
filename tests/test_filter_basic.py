"""
Basic filter tests - include/exclude fundamentals.
"""
import pytest
from data_builder import DataBuilder, generate_user


class TestFilterBasic:
    """Test basic include/exclude filter functionality."""

    def test_empty_filter_returns_all_users(self, api, clean_db):
        """With no filters, all users in the community should be returned."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(10)
        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 10

    def test_filter_requires_community(self, api, clean_db):
        """Without community, no users should be returned."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(10)
        builder.build()

        # Clear the current_community config
        api.set_community('')

        users = api.filter_users({
            'communitySlug': '',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 0

    def test_filter_only_returns_current_community(self, api, clean_db):
        """Users from other communities should not be returned."""
        # Add users to two different communities
        builder1 = DataBuilder(api)
        builder1.with_community('comm-alpha')
        builder1.with_fetch('members')
        builder1.with_users(5)
        builder1.build()

        builder2 = DataBuilder(api)
        builder2.with_community('comm-beta')
        builder2.with_fetch('members')
        builder2.with_users(8)
        builder2.build()

        # Filter for alpha
        users = api.filter_users({
            'communitySlug': 'comm-alpha',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 5

        # Filter for beta
        users = api.filter_users({
            'communitySlug': 'comm-beta',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 8

    def test_include_and_exclude_can_be_combined(self, api, clean_db):
        """Include and exclude filters can work together."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # Add admins with high points
        for _ in range(3):
            builder.with_specific_user(role='admin', points=1000)

        # Add admins with low points
        for _ in range(2):
            builder.with_specific_user(role='admin', points=50)

        # Add members with high points
        for _ in range(5):
            builder.with_specific_user(role='member', points=1500)

        builder.build()

        # Include only admins, exclude those with less than 500 points
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': 'admin'},
            'exclude': {'points_max': 499}
        })

        assert len(users) == 3
        for u in users:
            assert u['member_role'] == 'admin'
            assert u['points'] >= 500

    def test_deduplication_returns_latest_user_snapshot(self, api, clean_db):
        """When same user appears in multiple fetches, return latest."""
        skool_id = 'usr_dedup_test'

        # First fetch - user with 100 points
        api.bulk_fetches([{
            'type': 'members',
            'community_slug': 'test-comm',
            'page_param': 1,
            'raw_data': '{}',
            'status': 'ok'
        }])

        api.bulk_users([{
            'fetch_id': 1,
            'fetched_at': 1000,
            'community_slug': 'test-comm',
            'skool_id': skool_id,
            'name': 'testuser',
            'member_role': 'member',
            'points': 100,
            'last_active': 1000,
            'member_created_at': 500
        }])

        # Second fetch - same user with 200 points
        api.bulk_users([{
            'fetch_id': 1,
            'fetched_at': 2000,
            'community_slug': 'test-comm',
            'skool_id': skool_id,
            'name': 'testuser',
            'member_role': 'member',
            'points': 200,
            'last_active': 2000,
            'member_created_at': 500
        }])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {}
        })

        # Should only return 1 user (deduplicated)
        assert len(users) == 1
        # Should have the latest points value
        assert users[0]['points'] == 200

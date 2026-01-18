"""
Sorting tests.
"""
import pytest
from data_builder import DataBuilder
import time

NOW = int(time.time())
DAY = 86400


class TestFilterSort:
    """Test sortBy functionality."""

    def test_sort_by_name_asc(self, api, clean_db):
        """Sort by name ascending (A-Z)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'charlie', 'first_name': 'C',
                'last_name': 'Test', 'email': 'c@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'alice', 'first_name': 'A',
                'last_name': 'Test', 'email': 'a@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'bob', 'first_name': 'B',
                'last_name': 'Test', 'email': 'b@test.com', 'member_role': 'member',
                'points': 300, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'name_asc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['name'] == 'alice'
        assert users[1]['name'] == 'bob'
        assert users[2]['name'] == 'charlie'

    def test_sort_by_name_desc(self, api, clean_db):
        """Sort by name descending (Z-A)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'alice', 'first_name': 'A',
                'last_name': 'Test', 'email': 'a@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'charlie', 'first_name': 'C',
                'last_name': 'Test', 'email': 'c@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'bob', 'first_name': 'B',
                'last_name': 'Test', 'email': 'b@test.com', 'member_role': 'member',
                'points': 300, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'name_desc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['name'] == 'charlie'
        assert users[1]['name'] == 'bob'
        assert users[2]['name'] == 'alice'

    def test_sort_by_points_desc(self, api, clean_db):
        """Sort by points descending (highest first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'low', 'first_name': 'L',
                'last_name': 'Test', 'email': 'l@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'high', 'first_name': 'H',
                'last_name': 'Test', 'email': 'h@test.com', 'member_role': 'member',
                'points': 5000, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'medium', 'first_name': 'M',
                'last_name': 'Test', 'email': 'm@test.com', 'member_role': 'member',
                'points': 1000, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'points_desc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['points'] == 5000
        assert users[1]['points'] == 1000
        assert users[2]['points'] == 100

    def test_sort_by_points_asc(self, api, clean_db):
        """Sort by points ascending (lowest first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'high', 'first_name': 'H',
                'last_name': 'Test', 'email': 'h@test.com', 'member_role': 'member',
                'points': 5000, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'low', 'first_name': 'L',
                'last_name': 'Test', 'email': 'l@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'medium', 'first_name': 'M',
                'last_name': 'Test', 'email': 'm@test.com', 'member_role': 'member',
                'points': 1000, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'points_asc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['points'] == 100
        assert users[1]['points'] == 1000
        assert users[2]['points'] == 5000

    def test_sort_by_last_active_desc(self, api, clean_db):
        """Sort by last active descending (most recent first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'old', 'first_name': 'O',
                'last_name': 'Test', 'email': 'o@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW - 90*DAY, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'recent', 'first_name': 'R',
                'last_name': 'Test', 'email': 'r@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW - 1*DAY, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'middle', 'first_name': 'M',
                'last_name': 'Test', 'email': 'm@test.com', 'member_role': 'member',
                'points': 300, 'last_active': NOW - 30*DAY, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'last_active_desc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['name'] == 'recent'
        assert users[1]['name'] == 'middle'
        assert users[2]['name'] == 'old'

    def test_sort_by_last_active_asc(self, api, clean_db):
        """Sort by last active ascending (oldest activity first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'recent', 'first_name': 'R',
                'last_name': 'Test', 'email': 'r@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW - 1*DAY, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'old', 'first_name': 'O',
                'last_name': 'Test', 'email': 'o@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW - 90*DAY, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'last_active_asc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 2
        assert users[0]['name'] == 'old'
        assert users[1]['name'] == 'recent'

    def test_sort_by_joined_desc(self, api, clean_db):
        """Sort by join date descending (newest members first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'veteran', 'first_name': 'V',
                'last_name': 'Test', 'email': 'v@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 365*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'newbie', 'first_name': 'N',
                'last_name': 'Test', 'email': 'n@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 7*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'middle', 'first_name': 'M',
                'last_name': 'Test', 'email': 'm@test.com', 'member_role': 'member',
                'points': 300, 'last_active': NOW, 'member_created_at': NOW - 90*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'joined_desc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 3
        assert users[0]['name'] == 'newbie'
        assert users[1]['name'] == 'middle'
        assert users[2]['name'] == 'veteran'

    def test_sort_by_joined_asc(self, api, clean_db):
        """Sort by join date ascending (oldest members first)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'newbie', 'first_name': 'N',
                'last_name': 'Test', 'email': 'n@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 7*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'veteran', 'first_name': 'V',
                'last_name': 'Test', 'email': 'v@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 365*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'joined_asc',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 2
        assert users[0]['name'] == 'veteran'
        assert users[1]['name'] == 'newbie'

    def test_default_sort_is_name_asc(self, api, clean_db):
        """When no sort specified, default should be name_asc."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'zoe', 'first_name': 'Z',
                'last_name': 'Test', 'email': 'z@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'alice', 'first_name': 'A',
                'last_name': 'Test', 'email': 'a@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        # No sortBy specified
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 2
        assert users[0]['name'] == 'alice'
        assert users[1]['name'] == 'zoe'

    def test_invalid_sort_falls_back_to_default(self, api, clean_db):
        """Invalid sort value should fall back to default (name_asc)."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'zoe', 'first_name': 'Z',
                'last_name': 'Test', 'email': 'z@test.com', 'member_role': 'member',
                'points': 100, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            },
            {
                'fetch_id': 1, 'fetched_at': NOW, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'alice', 'first_name': 'A',
                'last_name': 'Test', 'email': 'a@test.com', 'member_role': 'member',
                'points': 200, 'last_active': NOW, 'member_created_at': NOW - 100*DAY
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'sortBy': 'invalid_sort_value',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 2
        # Should fall back to name ASC
        assert users[0]['name'] == 'alice'

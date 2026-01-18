"""
Search term filter tests.
"""
import pytest
from data_builder import DataBuilder


class TestFilterSearch:
    """Test searchTerm filtering."""

    def test_search_by_username(self, api, clean_db):
        """Search should match username."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # Add users with different names
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'johndoe', 'first_name': 'John',
                'last_name': 'Doe', 'email': 'john@test.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'janedoe', 'first_name': 'Jane',
                'last_name': 'Doe', 'email': 'jane@test.com', 'member_role': 'member',
                'points': 200, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_3', 'name': 'bobsmith', 'first_name': 'Bob',
                'last_name': 'Smith', 'email': 'bob@test.com', 'member_role': 'member',
                'points': 300, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'john',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1
        assert users[0]['name'] == 'johndoe'

    def test_search_by_first_name(self, api, clean_db):
        """Search should match first name."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'user1', 'first_name': 'Alexander',
                'last_name': 'Test', 'email': 'alex@test.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'user2', 'first_name': 'Bob',
                'last_name': 'Test', 'email': 'bob@test.com', 'member_role': 'member',
                'points': 200, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'Alex',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1
        assert users[0]['first_name'] == 'Alexander'

    def test_search_by_last_name(self, api, clean_db):
        """Search should match last name."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'user1', 'first_name': 'Test',
                'last_name': 'Johnson', 'email': 'a@test.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'user2', 'first_name': 'Test',
                'last_name': 'Williams', 'email': 'b@test.com', 'member_role': 'member',
                'points': 200, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'Johnson',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1
        assert users[0]['last_name'] == 'Johnson'

    def test_search_by_email(self, api, clean_db):
        """Search should match email."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'user1', 'first_name': 'A',
                'last_name': 'B', 'email': 'special@unique.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'user2', 'first_name': 'C',
                'last_name': 'D', 'email': 'normal@test.com', 'member_role': 'member',
                'points': 200, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'unique',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1
        assert 'unique' in users[0]['email']

    def test_search_case_insensitive(self, api, clean_db):
        """Search should be case-insensitive."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'JohnDoe', 'first_name': 'John',
                'last_name': 'Doe', 'email': 'john@test.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        # Lowercase search for mixed-case name
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'johndoe',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1

        # Uppercase search
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'JOHNDOE',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1

    def test_search_partial_match(self, api, clean_db):
        """Search should match partial strings."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'christopher', 'first_name': 'Christopher',
                'last_name': 'Anderson', 'email': 'chris@test.com', 'member_role': 'member',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        # Partial match
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'chris',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 1

    def test_search_with_filters(self, api, clean_db):
        """Search should work together with other filters."""
        api.bulk_users([
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_1', 'name': 'johnadmin', 'first_name': 'John',
                'last_name': 'Admin', 'email': 'john@test.com', 'member_role': 'admin',
                'points': 100, 'last_active': 1000, 'member_created_at': 500
            },
            {
                'fetch_id': 1, 'fetched_at': 1000, 'community_slug': 'test-comm',
                'skool_id': 'usr_2', 'name': 'johnmember', 'first_name': 'John',
                'last_name': 'Member', 'email': 'johnm@test.com', 'member_role': 'member',
                'points': 200, 'last_active': 1000, 'member_created_at': 500
            }
        ])

        api.set_community('test-comm')

        # Search for "john" but only admins
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'john',
            'include': {'member_role': 'admin'},
            'exclude': {}
        })

        assert len(users) == 1
        assert users[0]['member_role'] == 'admin'

    def test_empty_search_returns_all(self, api, clean_db):
        """Empty search term should return all users."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(5)
        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': '',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 5

    def test_no_match_returns_empty(self, api, clean_db):
        """Search with no matches should return empty list."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(5)
        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'searchTerm': 'nonexistentuserxyz123',
            'include': {},
            'exclude': {}
        })

        assert len(users) == 0

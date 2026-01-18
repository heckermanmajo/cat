"""
Role-based filter tests.
"""
import pytest
from data_builder import DataBuilder


class TestFilterRole:
    """Test member_role filtering."""

    def test_include_admin_role(self, api, clean_db):
        """Include only admins."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(3):
            builder.with_specific_user(role='admin')
        for _ in range(5):
            builder.with_specific_user(role='moderator')
        for _ in range(10):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': 'admin'},
            'exclude': {}
        })

        assert len(users) == 3
        for u in users:
            assert u['member_role'] == 'admin'

    def test_include_moderator_role(self, api, clean_db):
        """Include only moderators."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(2):
            builder.with_specific_user(role='admin')
        for _ in range(4):
            builder.with_specific_user(role='moderator')
        for _ in range(8):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': 'moderator'},
            'exclude': {}
        })

        assert len(users) == 4
        for u in users:
            assert u['member_role'] == 'moderator'

    def test_include_member_role(self, api, clean_db):
        """Include only regular members."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(2):
            builder.with_specific_user(role='admin')
        for _ in range(3):
            builder.with_specific_user(role='moderator')
        for _ in range(15):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': 'member'},
            'exclude': {}
        })

        assert len(users) == 15
        for u in users:
            assert u['member_role'] == 'member'

    def test_exclude_admin_role(self, api, clean_db):
        """Exclude admins - should return moderators and members."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(3):
            builder.with_specific_user(role='admin')
        for _ in range(4):
            builder.with_specific_user(role='moderator')
        for _ in range(10):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'member_role': 'admin'}
        })

        assert len(users) == 14  # 4 + 10
        for u in users:
            assert u['member_role'] != 'admin'

    def test_exclude_member_role(self, api, clean_db):
        """Exclude regular members - should return admins and moderators."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(2):
            builder.with_specific_user(role='admin')
        for _ in range(5):
            builder.with_specific_user(role='moderator')
        for _ in range(20):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'member_role': 'member'}
        })

        assert len(users) == 7  # 2 + 5
        for u in users:
            assert u['member_role'] in ['admin', 'moderator']

    def test_conflicting_include_exclude_same_role(self, api, clean_db):
        """Including and excluding same role should return empty."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(5):
            builder.with_specific_user(role='admin')
        for _ in range(5):
            builder.with_specific_user(role='member')

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': 'admin'},
            'exclude': {'member_role': 'admin'}
        })

        # This is a contradiction - include admin AND exclude admin
        assert len(users) == 0

    def test_role_filter_with_minus_one_is_ignored(self, api, clean_db):
        """Role filter with -1 or '-1' should be ignored (any role)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(3):
            builder.with_specific_user(role='admin')
        for _ in range(7):
            builder.with_specific_user(role='member')

        builder.build()

        # -1 as integer
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': -1},
            'exclude': {}
        })
        assert len(users) == 10

        # '-1' as string
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'member_role': '-1'},
            'exclude': {}
        })
        assert len(users) == 10

"""
Date-based filter tests (active_since, inactive_since, joined_since, joined_before).
"""
import pytest
from data_builder import DataBuilder


class TestFilterActiveSince:
    """Test active_since filter - users active in last X days."""

    def test_include_active_in_last_7_days(self, api, clean_db):
        """Include users active in the last 7 days."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 5 users active in last 7 days
        for _ in range(5):
            builder.with_specific_user(last_active_days_ago=3)

        # 10 users inactive for 30+ days
        for _ in range(10):
            builder.with_specific_user(last_active_days_ago=45)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'active_since': 7},
            'exclude': {}
        })

        assert len(users) == 5

    def test_include_active_in_last_30_days(self, api, clean_db):
        """Include users active in the last 30 days."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 8 users active in last 30 days
        for _ in range(3):
            builder.with_specific_user(last_active_days_ago=5)
        for _ in range(5):
            builder.with_specific_user(last_active_days_ago=20)

        # 7 users inactive for 60+ days
        for _ in range(7):
            builder.with_specific_user(last_active_days_ago=90)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'active_since': 30},
            'exclude': {}
        })

        assert len(users) == 8

    def test_exclude_active_in_last_7_days(self, api, clean_db):
        """Exclude users active in last 7 days (get inactive users)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 4 active users
        for _ in range(4):
            builder.with_specific_user(last_active_days_ago=2)

        # 6 inactive users
        for _ in range(6):
            builder.with_specific_user(last_active_days_ago=30)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'active_since': 7}
        })

        # Should return users NOT active in last 7 days
        assert len(users) == 6


class TestFilterInactiveSince:
    """Test inactive_since filter - users NOT active for X days."""

    def test_include_inactive_for_30_days(self, api, clean_db):
        """Include users inactive for 30+ days."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 5 active users (last 7 days)
        for _ in range(5):
            builder.with_specific_user(last_active_days_ago=3)

        # 8 inactive users (30+ days)
        for _ in range(8):
            builder.with_specific_user(last_active_days_ago=45)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'inactive_since': 30},
            'exclude': {}
        })

        assert len(users) == 8

    def test_exclude_inactive_for_30_days(self, api, clean_db):
        """Exclude users inactive for 30+ days (get active users)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 6 active users
        for _ in range(6):
            builder.with_specific_user(last_active_days_ago=10)

        # 4 inactive users
        for _ in range(4):
            builder.with_specific_user(last_active_days_ago=60)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'inactive_since': 30}
        })

        # Should return users who ARE active (not inactive for 30 days)
        assert len(users) == 6


class TestFilterJoinedSince:
    """Test joined_since filter - users who joined in last X days."""

    def test_include_joined_in_last_30_days(self, api, clean_db):
        """Include users who joined in the last 30 days."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 4 new users (joined in last 30 days)
        for _ in range(4):
            builder.with_specific_user(joined_days_ago=15)

        # 10 old users (joined 60+ days ago)
        for _ in range(10):
            builder.with_specific_user(joined_days_ago=90)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'joined_since': 30},
            'exclude': {}
        })

        assert len(users) == 4

    def test_exclude_joined_in_last_30_days(self, api, clean_db):
        """Exclude new users (get established members)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 3 new users
        for _ in range(3):
            builder.with_specific_user(joined_days_ago=10)

        # 7 established users
        for _ in range(7):
            builder.with_specific_user(joined_days_ago=120)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'joined_since': 30}
        })

        assert len(users) == 7


class TestFilterJoinedBefore:
    """Test joined_before filter - users who joined before X days ago."""

    def test_include_joined_before_90_days(self, api, clean_db):
        """Include users who joined more than 90 days ago."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 5 veteran users (joined 100+ days ago)
        for _ in range(5):
            builder.with_specific_user(joined_days_ago=150)

        # 8 newer users (joined 30 days ago)
        for _ in range(8):
            builder.with_specific_user(joined_days_ago=30)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'joined_before': 90},
            'exclude': {}
        })

        assert len(users) == 5

    def test_exclude_joined_before_90_days(self, api, clean_db):
        """Exclude veterans (get newer members)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 4 veterans
        for _ in range(4):
            builder.with_specific_user(joined_days_ago=180)

        # 6 newer users
        for _ in range(6):
            builder.with_specific_user(joined_days_ago=45)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'joined_before': 90}
        })

        assert len(users) == 6


class TestFilterDateCombinations:
    """Test combining multiple date filters."""

    def test_active_and_joined_recently(self, api, clean_db):
        """Find users who are both active AND joined recently."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # New and active (should match)
        for _ in range(3):
            builder.with_specific_user(joined_days_ago=15, last_active_days_ago=2)

        # New but inactive (should not match)
        for _ in range(4):
            builder.with_specific_user(joined_days_ago=10, last_active_days_ago=60)

        # Old but active (should not match)
        for _ in range(5):
            builder.with_specific_user(joined_days_ago=120, last_active_days_ago=3)

        # Old and inactive (should not match)
        for _ in range(2):
            builder.with_specific_user(joined_days_ago=200, last_active_days_ago=90)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {
                'joined_since': 30,
                'active_since': 7
            },
            'exclude': {}
        })

        assert len(users) == 3

    def test_string_values_for_days(self, api, clean_db):
        """Days filters should work with string values (from frontend)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(5):
            builder.with_specific_user(last_active_days_ago=3)
        for _ in range(5):
            builder.with_specific_user(last_active_days_ago=60)

        builder.build()

        # String '7' should work like integer 7
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'active_since': '7'},
            'exclude': {}
        })

        assert len(users) == 5

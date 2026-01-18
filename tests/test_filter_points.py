"""
Points-based filter tests (points_min, points_max).
"""
import pytest
from data_builder import DataBuilder


class TestFilterPointsMin:
    """Test points_min filter - minimum points threshold."""

    def test_include_points_min_500(self, api, clean_db):
        """Include only users with 500+ points."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 5 high-point users
        for _ in range(5):
            builder.with_specific_user(points=1000)

        # 8 low-point users
        for _ in range(8):
            builder.with_specific_user(points=100)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'points_min': 500},
            'exclude': {}
        })

        assert len(users) == 5
        for u in users:
            assert u['points'] >= 500

    def test_include_points_min_zero(self, api, clean_db):
        """Include users with 0+ points (everyone)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(3):
            builder.with_specific_user(points=0)
        for _ in range(7):
            builder.with_specific_user(points=500)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'points_min': 0},
            'exclude': {}
        })

        assert len(users) == 10

    def test_exclude_points_min_500(self, api, clean_db):
        """Exclude users with 500+ points (get low-point users)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(4):
            builder.with_specific_user(points=800)
        for _ in range(6):
            builder.with_specific_user(points=200)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'points_min': 500}
        })

        # Exclude those with >= 500 points = get those with < 500
        assert len(users) == 6
        for u in users:
            assert u['points'] < 500


class TestFilterPointsMax:
    """Test points_max filter - maximum points threshold."""

    def test_include_points_max_500(self, api, clean_db):
        """Include only users with <= 500 points."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # 6 low-point users
        for _ in range(6):
            builder.with_specific_user(points=300)

        # 4 high-point users
        for _ in range(4):
            builder.with_specific_user(points=1000)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'points_max': 500},
            'exclude': {}
        })

        assert len(users) == 6
        for u in users:
            assert u['points'] <= 500

    def test_exclude_points_max_500(self, api, clean_db):
        """Exclude users with <= 500 points (get high-point users)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(5):
            builder.with_specific_user(points=200)
        for _ in range(5):
            builder.with_specific_user(points=1500)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {'points_max': 500}
        })

        # Exclude those with <= 500 = get those with > 500
        assert len(users) == 5
        for u in users:
            assert u['points'] > 500


class TestFilterPointsRange:
    """Test combining points_min and points_max for ranges."""

    def test_points_between_200_and_800(self, api, clean_db):
        """Include users with points between 200 and 800."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        # Below range
        for _ in range(3):
            builder.with_specific_user(points=50)

        # In range
        for _ in range(5):
            builder.with_specific_user(points=500)

        # Above range
        for _ in range(4):
            builder.with_specific_user(points=1500)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {
                'points_min': 200,
                'points_max': 800
            },
            'exclude': {}
        })

        assert len(users) == 5
        for u in users:
            assert 200 <= u['points'] <= 800

    def test_exact_boundary_values(self, api, clean_db):
        """Test that exact boundary values are included."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        builder.with_specific_user(points=100)  # Exactly at min
        builder.with_specific_user(points=500)  # Exactly at max
        builder.with_specific_user(points=300)  # In between
        builder.with_specific_user(points=99)   # Just below min
        builder.with_specific_user(points=501)  # Just above max

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {
                'points_min': 100,
                'points_max': 500
            },
            'exclude': {}
        })

        assert len(users) == 3
        points_list = [u['points'] for u in users]
        assert 100 in points_list
        assert 500 in points_list
        assert 300 in points_list

    def test_string_values_for_points(self, api, clean_db):
        """Points filters should work with string values (from frontend)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(4):
            builder.with_specific_user(points=1000)
        for _ in range(6):
            builder.with_specific_user(points=100)

        builder.build()

        # String '500' should work like integer 500
        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {'points_min': '500'},
            'exclude': {}
        })

        assert len(users) == 4

    def test_impossible_range_returns_empty(self, api, clean_db):
        """When min > max, should return empty (impossible range)."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(10):
            builder.with_specific_user(points=500)

        builder.build()

        users = api.filter_users({
            'communitySlug': 'test-comm',
            'include': {
                'points_min': 800,
                'points_max': 200
            },
            'exclude': {}
        })

        # min=800, max=200 is impossible - no user can have >= 800 AND <= 200
        assert len(users) == 0

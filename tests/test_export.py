"""
CSV export tests.
"""
import pytest
import csv
import io
from data_builder import DataBuilder


class TestExport:
    """Test CSV export functionality."""

    def test_export_csv_returns_csv_content(self, api, clean_db):
        """Export should return valid CSV content."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(5)
        builder.build()

        response = api.post('/api/user/export-csv', json={
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {}
        })

        assert response.status_code == 200
        assert 'text/csv' in response.headers.get('Content-Type', '')

        # Parse CSV content
        content = response.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Header + 5 data rows
        assert len(rows) == 6

        # Check header
        header = rows[0]
        assert 'name' in header
        assert 'email' in header
        assert 'member_role' in header
        assert 'points' in header

    def test_export_csv_with_filters(self, api, clean_db):
        """Export should respect filters."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')

        for _ in range(3):
            builder.with_specific_user(role='admin')
        for _ in range(7):
            builder.with_specific_user(role='member')

        builder.build()

        response = api.post('/api/user/export-csv', json={
            'communitySlug': 'test-comm',
            'include': {'member_role': 'admin'},
            'exclude': {}
        })

        assert response.status_code == 200

        content = response.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Header + 3 admin rows
        assert len(rows) == 4

    def test_export_csv_empty_result(self, api, clean_db):
        """Export with no matching users should return header only."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(5, role='member')
        builder.build()

        response = api.post('/api/user/export-csv', json={
            'communitySlug': 'test-comm',
            'include': {'member_role': 'admin'},  # No admins exist
            'exclude': {}
        })

        assert response.status_code == 200

        content = response.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Just header
        assert len(rows) == 1

    def test_export_csv_content_disposition(self, api, clean_db):
        """Export should have proper Content-Disposition header."""
        builder = DataBuilder(api)
        builder.with_community('test-comm')
        builder.with_fetch('members')
        builder.with_users(3)
        builder.build()

        response = api.post('/api/user/export-csv', json={
            'communitySlug': 'test-comm',
            'include': {},
            'exclude': {}
        })

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert 'filename=' in content_disposition

"""
Pytest configuration and fixtures for API testing.
"""
import pytest
import requests
import time
import os

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:3000')


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """Wait for the server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/api/configentry", timeout=2)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope='session')
def api():
    """API client fixture - provides helper methods for API calls."""
    class APIClient:
        def __init__(self, base_url: str):
            self.base_url = base_url

        def get(self, path: str) -> requests.Response:
            return requests.get(f"{self.base_url}{path}")

        def post(self, path: str, json: dict = None) -> requests.Response:
            return requests.post(f"{self.base_url}{path}", json=json)

        def put(self, path: str, json: dict = None) -> requests.Response:
            return requests.put(f"{self.base_url}{path}", json=json)

        def delete(self, path: str) -> requests.Response:
            return requests.delete(f"{self.base_url}{path}")

        def reset(self):
            """Clear all test data."""
            r = self.post('/api/test/reset')
            assert r.status_code == 200, f"Reset failed: {r.text}"

        def set_community(self, slug: str):
            """Set the current community."""
            r = self.post('/api/test/set-community', json={'slug': slug})
            assert r.status_code == 200, f"Set community failed: {r.text}"

        def filter_users(self, filter_state: dict) -> list:
            """Filter users with given filter state."""
            r = self.post('/api/user/filter', json=filter_state)
            assert r.status_code == 200, f"Filter failed: {r.text}"
            return r.json()

        def bulk_users(self, users: list) -> dict:
            """Insert multiple users."""
            r = self.post('/api/test/bulk-users', json={'users': users})
            assert r.status_code == 200, f"Bulk users failed: {r.text}"
            return r.json()

        def bulk_posts(self, posts: list) -> dict:
            """Insert multiple posts."""
            r = self.post('/api/test/bulk-posts', json={'posts': posts})
            assert r.status_code == 200, f"Bulk posts failed: {r.text}"
            return r.json()

        def bulk_likes(self, likes: list) -> dict:
            """Insert multiple likes."""
            r = self.post('/api/test/bulk-likes', json={'likes': likes})
            assert r.status_code == 200, f"Bulk likes failed: {r.text}"
            return r.json()

        def bulk_profiles(self, profiles: list) -> dict:
            """Insert multiple profiles."""
            r = self.post('/api/test/bulk-profiles', json={'profiles': profiles})
            assert r.status_code == 200, f"Bulk profiles failed: {r.text}"
            return r.json()

        def bulk_fetches(self, fetches: list) -> dict:
            """Insert multiple fetches."""
            r = self.post('/api/test/bulk-fetches', json={'fetches': fetches})
            assert r.status_code == 200, f"Bulk fetches failed: {r.text}"
            return r.json()

    # Wait for server to be ready
    if not wait_for_server(BASE_URL):
        pytest.fail(f"Server at {BASE_URL} not ready after 30s")

    return APIClient(BASE_URL)


@pytest.fixture(scope='function')
def clean_db(api):
    """Reset the database before each test."""
    api.reset()
    yield
    # Optionally reset after test too
    # api.reset()

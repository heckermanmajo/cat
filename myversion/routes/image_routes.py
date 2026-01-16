"""
Profilbild-Caching: Lädt Bilder von Skool und cached sie lokal.
"""
import os
import requests
from flask import send_file, redirect
from src.config_entry import ConfigEntry
from src.user import User

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'images')


def get_cached_path(skool_id: str) -> str:
    """Returns path to cached image file."""
    return os.path.join(CACHE_DIR, f"{skool_id}.jpg")


def download_image(url: str, skool_id: str) -> str | None:
    """Downloads image from URL and saves to cache. Returns path or None on error."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        path = get_cached_path(skool_id)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(resp.content)
        return path
    except Exception:
        return None


def register(app):
    @app.route('/api/image/<skool_id>')
    def get_image(skool_id: str):
        """
        Returns cached profile image or downloads it first.
        If caching disabled: redirects to original URL.
        If no image available: returns 404.
        """
        # Check if caching is enabled
        config = ConfigEntry.getByKey('cache_profile_images')
        caching_enabled = config and config.value == '1'

        # Find user and their picture_url
        users = User.get_list(
            "SELECT * FROM user WHERE skool_id = ? ORDER BY created_at DESC LIMIT 1",
            [skool_id]
        )
        if not users:
            return 'User not found', 404

        picture_url = users[0].picture_url
        if not picture_url:
            return 'No profile image', 404

        # If caching disabled: redirect to original
        if not caching_enabled:
            return redirect(picture_url)

        # Check cache
        cached_path = get_cached_path(skool_id)
        if os.path.exists(cached_path):
            return send_file(cached_path, mimetype='image/jpeg')

        # Download and cache
        path = download_image(picture_url, skool_id)
        if path:
            return send_file(path, mimetype='image/jpeg')

        # Fallback: redirect to original
        return redirect(picture_url)

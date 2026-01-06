"""
CatKnows License Module

Handles license validation against the remote server and local caching.
"""

import json
import secrets
import socket
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional
import requests


# Configuration
LICENSE_SERVER_URL = 'https://catknows.hackerman.de/validate.php'
REVALIDATION_DAYS = 7  # Revalidate every 7 days
GRACE_PERIOD_DAYS = 7  # Allow 7 days after expiration
REQUEST_TIMEOUT = 5    # Seconds


def get_machine_id() -> str:
    """Generate a unique machine identifier based on hardware info."""
    try:
        mac = uuid.getnode()
        hostname = socket.gethostname()
        raw = f"{mac}-{hostname}"
        return hashlib.sha256(raw.encode()).hexdigest()
    except Exception:
        # Fallback if we can't get hardware info
        return hashlib.sha256(socket.gethostname().encode()).hexdigest()


def get_stored_license(db) -> Optional[dict]:
    """Get the stored license from database."""
    row = db.execute('SELECT * FROM license LIMIT 1').fetchone()
    if not row:
        return None
    return {
        'id': row['id'],
        'license_key': row['license_key'],
        'valid_until': row['valid_until'],
        'features': json.loads(row['features'] or '[]'),
        'last_validated': row['last_validated'],
        'server_reachable': bool(row['server_reachable']),
        'activated_at': row['activated_at']
    }


def save_license(db, key: str, valid_until: str, features: list):
    """Save or update license in database."""
    now = datetime.now().isoformat()

    # Delete existing license (only one allowed)
    db.execute('DELETE FROM license')

    # Insert new license
    db.execute('''
        INSERT INTO license (license_key, valid_until, features, last_validated, server_reachable, activated_at)
        VALUES (?, ?, ?, ?, 1, ?)
    ''', (key, valid_until, json.dumps(features), now, now))
    db.commit()


def update_license_validation(db, valid_until: str, features: list, server_reachable: bool):
    """Update license after validation."""
    now = datetime.now().isoformat()
    db.execute('''
        UPDATE license
        SET valid_until = ?, features = ?, last_validated = ?, server_reachable = ?
    ''', (valid_until, json.dumps(features), now, 1 if server_reachable else 0))
    db.commit()


def update_server_status(db, reachable: bool):
    """Update only the server reachable status."""
    db.execute('UPDATE license SET server_reachable = ?', (1 if reachable else 0,))
    db.commit()


def should_revalidate(last_validated: Optional[str]) -> bool:
    """Check if we should revalidate the license (>7 days since last check)."""
    if not last_validated:
        return True

    try:
        last_dt = datetime.fromisoformat(last_validated.replace('Z', '+00:00'))
        # Make naive if timezone-aware for comparison
        if last_dt.tzinfo is not None:
            last_dt = last_dt.replace(tzinfo=None)
        return datetime.now() - last_dt > timedelta(days=REVALIDATION_DAYS)
    except Exception:
        return True


def is_within_grace_period(valid_until: str) -> bool:
    """Check if license is within the 7-day grace period after expiration."""
    try:
        expiry = datetime.strptime(valid_until, '%Y-%m-%d').date()
        today = datetime.now().date()
        days_expired = (today - expiry).days
        return 0 < days_expired <= GRACE_PERIOD_DAYS
    except Exception:
        return False


def validate_with_server(license_key: str) -> dict:
    """
    Validate license against the remote server.

    Returns:
        dict with 'success', 'payload' or 'error'
    """
    nonce = secrets.token_hex(32)  # 64 hex chars
    machine_id = get_machine_id()

    try:
        response = requests.post(
            LICENSE_SERVER_URL,
            json={
                'license_key': license_key,
                'nonce': nonce,
                'machine_id': machine_id
            },
            timeout=REQUEST_TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            data = response.json()
            return {'success': True, 'data': data}
        else:
            return {'success': False, 'error': f'Server returned {response.status_code}'}

    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'timeout'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'connection_error'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def check_license(db) -> dict:
    """
    Main license check function.

    Returns:
        dict: {
            'has_license': bool,
            'is_valid': bool,
            'in_grace_period': bool,
            'valid_until': str | None,
            'features': list,
            'server_status': 'online' | 'offline' | 'not_checked',
            'message': str
        }
    """
    result = {
        'has_license': False,
        'is_valid': False,
        'in_grace_period': False,
        'valid_until': None,
        'features': [],
        'server_status': 'not_checked',
        'message': '',
        'license_key': None,
        'last_validated': None
    }

    # Get stored license
    stored = get_stored_license(db)

    if not stored:
        result['message'] = 'Keine Lizenz aktiviert'
        return result

    result['has_license'] = True
    result['license_key'] = stored['license_key']
    result['valid_until'] = stored['valid_until']
    result['features'] = stored['features']
    result['last_validated'] = stored['last_validated']

    # Check if revalidation is needed
    if should_revalidate(stored['last_validated']):
        # Try to validate with server
        server_result = validate_with_server(stored['license_key'])

        if server_result['success']:
            result['server_status'] = 'online'
            payload = server_result['data'].get('payload', {})

            if payload.get('valid'):
                # Update local data
                update_license_validation(
                    db,
                    payload.get('expires_at', stored['valid_until']),
                    payload.get('features', []),
                    True
                )
                result['valid_until'] = payload.get('expires_at')
                result['features'] = payload.get('features', [])
                result['is_valid'] = True
                result['message'] = 'Lizenz gueltig'
            else:
                error = payload.get('error', 'unknown')
                update_server_status(db, True)

                if error == 'license_expired':
                    result['message'] = 'Lizenz abgelaufen'
                    # Check grace period
                    if is_within_grace_period(stored['valid_until']):
                        result['is_valid'] = True
                        result['in_grace_period'] = True
                        result['message'] = 'Lizenz abgelaufen (Grace-Period aktiv)'
                elif error == 'license_deactivated':
                    result['message'] = 'Lizenz wurde deaktiviert'
                else:
                    result['message'] = 'Lizenz ungueltig'
        else:
            # Server not reachable - use local data
            result['server_status'] = 'offline'
            update_server_status(db, False)

            # Check local validity
            if stored['valid_until']:
                try:
                    expiry = datetime.strptime(stored['valid_until'], '%Y-%m-%d').date()
                    today = datetime.now().date()

                    if today <= expiry:
                        result['is_valid'] = True
                        result['message'] = 'Lizenz gueltig (Offline-Modus)'
                    elif is_within_grace_period(stored['valid_until']):
                        result['is_valid'] = True
                        result['in_grace_period'] = True
                        result['message'] = 'Lizenz abgelaufen - Grace-Period aktiv (Offline-Modus)'
                    else:
                        result['message'] = 'Lizenz abgelaufen'
                except Exception:
                    result['message'] = 'Lizenz-Datum ungueltig'
    else:
        # No revalidation needed, use local data
        result['server_status'] = 'not_checked'

        if stored['valid_until']:
            try:
                expiry = datetime.strptime(stored['valid_until'], '%Y-%m-%d').date()
                today = datetime.now().date()

                if today <= expiry:
                    result['is_valid'] = True
                    result['message'] = 'Lizenz gueltig'
                elif is_within_grace_period(stored['valid_until']):
                    result['is_valid'] = True
                    result['in_grace_period'] = True
                    result['message'] = 'Lizenz abgelaufen - Grace-Period aktiv'
                else:
                    result['message'] = 'Lizenz abgelaufen'
            except Exception:
                result['message'] = 'Lizenz-Datum ungueltig'

    return result


def activate_license(db, license_key: str) -> dict:
    """
    Activate a new license.

    Returns:
        dict: {'success': bool, 'message': str, 'error': str | None}
    """
    # Validate with server
    server_result = validate_with_server(license_key)

    if not server_result['success']:
        error = server_result.get('error', 'unknown')
        if error == 'timeout' or error == 'connection_error':
            return {
                'success': False,
                'message': 'Lizenz-Server nicht erreichbar',
                'error': 'server_unreachable'
            }
        return {
            'success': False,
            'message': f'Verbindungsfehler: {error}',
            'error': 'connection_error'
        }

    payload = server_result['data'].get('payload', {})

    if payload.get('valid'):
        save_license(
            db,
            license_key,
            payload.get('expires_at', ''),
            payload.get('features', [])
        )
        return {
            'success': True,
            'message': 'Lizenz erfolgreich aktiviert!',
            'error': None
        }
    else:
        error = payload.get('error', 'unknown')
        error_messages = {
            'invalid_license': 'Ungueltiger Lizenz-Key',
            'license_expired': 'Lizenz ist abgelaufen',
            'license_deactivated': 'Lizenz wurde deaktiviert'
        }
        return {
            'success': False,
            'message': error_messages.get(error, 'Unbekannter Fehler'),
            'error': error
        }

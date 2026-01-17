from flask import jsonify, request
import os
import time
from datetime import datetime

LOG_FILE = 'logs.txt'

def log(msg: str, level: str = 'INFO'):
    """Append a log entry to logs.txt."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] [{level}] {msg}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line)

def register(app):
    @app.route('/api/logs')
    def get_logs():
        """Return logs as array of lines, newest first."""
        if not os.path.exists(LOG_FILE):
            return jsonify([])
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        lines = [l.rstrip('\n') for l in lines if l.strip()]
        lines.reverse()
        return jsonify(lines)

    @app.route('/api/logs/clear', methods=['POST'])
    def clear_logs():
        """Clear the logs file."""
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        log('Logs cleared', 'INFO')
        return jsonify({'status': 'ok'})

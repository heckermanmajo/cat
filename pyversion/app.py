#!/usr/bin/env python3
"""
CatKnows - Local Skool Analytics
Flask App, Pages, HTMX Routes
"""

import json
import re
import ssl
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Timer
from urllib.request import Request, urlopen

import certifi
from flask import Flask, render_template, request, g

import db
from db import get_db, close_db, get_setting, set_setting, log
from data import (
    get_available_communities, extract_filters_from_form,
    get_posts, get_members, get_communities, get_communities_with_shared_members,
    get_entities_overview, init_default_templates
)
from fetch_queue import reprocess_all_raw_fetches
from license import check_license, activate_license
from api import bp as api_bp


# SSL-Kontext mit certifi-Zertifikaten
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


# ============================================
# CONFIG
# ============================================

def get_data_dir():
    """Datenverzeichnis neben dem Binary"""
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / 'catknows_data'


DATA_DIR = get_data_dir()
DEFAULT_PORT = 3000

# DB-Pfade initialisieren
db.init_paths(DATA_DIR)


# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# API Blueprint registrieren
app.register_blueprint(api_bp, url_prefix='/api')

# DB Teardown
app.teardown_appcontext(close_db)


# ============================================
# CORS (für Browser Extension)
# ============================================

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS preflight requests"""
    return '', 204


# ============================================
# DATABASE INIT
# ============================================

def init_db():
    """Schema initialisieren"""
    with app.app_context():
        database = get_db()
        schema_path = Path(__file__).parent / 'schema.sql'
        if schema_path.exists():
            database.executescript(schema_path.read_text())
            database.commit()


# ============================================
# ROUTES - PAGES
# ============================================

@app.route('/')
def index():
    """Hauptseite - Chat View"""
    chats = get_db().execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    return render_template('chat.html', chats=chats)


@app.route('/settings')
def settings():
    """Settings View"""
    license_status = check_license(get_db())
    return render_template('settings.html',
        tab=request.args.get('tab', 'settings'),
        community_ids=get_setting('community_ids'),
        openai_api_key=get_setting('openai_api_key'),
        license=license_status
    )


@app.route('/filter')
def filter_page():
    """Filter View"""
    communities = get_available_communities()
    return render_template('filter.html',
        output_type='post',
        communities=communities
    )


# ============================================
# ROUTES - HTMX PARTIALS (Settings & License)
# ============================================

@app.route('/htmx/settings', methods=['POST'])
def htmx_save_setting():
    """Setting speichern - gibt Toast zurück"""
    key = request.form.get('key')
    value = request.form.get('value', '')
    set_setting(key, value)
    return render_template('partials/toast.html', message='Gespeichert!', type='success')


@app.route('/htmx/license/activate', methods=['POST'])
def htmx_license_activate():
    """Lizenz aktivieren via HTMX"""
    license_key = request.form.get('license_key', '').strip()

    if not license_key:
        return render_template('partials/toast.html',
            message='Bitte Lizenz-Key eingeben',
            type='error'
        )

    result = activate_license(get_db(), license_key)

    if result['success']:
        return '''
            <div class="toast success">Lizenz erfolgreich aktiviert!</div>
            <script>setTimeout(() => location.reload(), 1500)</script>
        '''
    else:
        return render_template('partials/toast.html',
            message=result['message'],
            type='error'
        )


# ============================================
# ROUTES - HTMX PARTIALS (Logs)
# ============================================

@app.route('/htmx/logs')
def htmx_logs():
    """Logs-Tabelle"""
    level = request.args.get('level', '')
    limit = int(request.args.get('limit', 50))

    query = 'SELECT * FROM logs WHERE 1=1'
    params = []
    if level:
        query += ' AND level = ?'
        params.append(level)
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)

    logs = get_db().execute(query, params).fetchall()
    return render_template('partials/logs_table.html', logs=logs)


@app.route('/htmx/logs/clear', methods=['DELETE'])
def htmx_clear_logs():
    get_db().execute('DELETE FROM logs')
    get_db().commit()
    return render_template('partials/logs_table.html', logs=[])


# ============================================
# ROUTES - HTMX PARTIALS (Entities)
# ============================================

@app.route('/htmx/entities')
def htmx_entities():
    """Entities-Übersicht anzeigen"""
    data = get_entities_overview()
    return render_template('partials/entities_view.html',
        stats=data['stats'],
        members=data['members'],
        posts=data['posts'],
        communities=data['communities']
    )


@app.route('/htmx/entities/reprocess', methods=['POST'])
def htmx_entities_reprocess():
    """Alle Entities neu extrahieren"""
    reprocess_all_raw_fetches()
    data = get_entities_overview()
    return render_template('partials/entities_view.html',
        stats=data['stats'],
        members=data['members'],
        posts=data['posts'],
        communities=data['communities']
    )


@app.route('/htmx/fetches')
def htmx_fetches():
    """Fetches-Tabelle"""
    entity_type = request.args.get('type', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = 'SELECT * FROM raw_fetches WHERE 1=1'
    params = []
    if entity_type:
        query += ' AND entity_type = ?'
        params.append(entity_type)
    query += ' ORDER BY fetched_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    fetches = get_db().execute(query, params).fetchall()
    types = get_db().execute('SELECT DISTINCT entity_type FROM raw_fetches').fetchall()

    return render_template('partials/fetches_table.html',
        fetches=fetches,
        entity_types=[t['entity_type'] for t in types],
        current_type=entity_type
    )


# ============================================
# ROUTES - HTMX PARTIALS (Filter)
# ============================================

@app.route('/htmx/filter/form')
def htmx_filter_form():
    """Dynamisches Filter-Formular nach Typ"""
    output_type = request.args.get('type', 'post')
    communities = get_available_communities()
    return render_template('partials/filter_form.html',
        output_type=output_type,
        communities=communities
    )


@app.route('/htmx/filter/preview', methods=['POST'])
def htmx_filter_preview():
    """Live-Vorschau der Filter-Ergebnisse"""
    output_type = request.form.get('output_type', 'post')
    filters = extract_filters_from_form(request.form, output_type)

    if output_type == 'post':
        results = get_posts(filters)
    elif output_type == 'member':
        results = get_members(filters)
    elif output_type == 'community':
        if filters.get('min_shared_members'):
            results = get_communities_with_shared_members(filters)
        else:
            results = get_communities(filters)
    else:
        results = []

    selection = {'name': 'Vorschau', 'output_type': output_type}

    return render_template('partials/selection_results.html',
        selection=selection,
        results=results[:100],
        total=len(results)
    )


@app.route('/htmx/filter/save', methods=['POST'])
def htmx_filter_save():
    """Filter als Selektion speichern"""
    name = request.form.get('selection_name')
    if not name:
        return render_template('partials/toast.html', message='Name erforderlich!', type='error')

    output_type = request.form.get('output_type', 'post')
    filters = extract_filters_from_form(request.form, output_type)

    database = get_db()
    database.execute('''
        INSERT INTO selections (name, output_type, filters_json, created_by)
        VALUES (?, ?, ?, ?)
    ''', (name, output_type, json.dumps(filters), 'user'))
    database.commit()

    return render_template('partials/toast.html', message=f'Selektion "{name}" gespeichert!', type='success')


# ============================================
# ROUTES - HTMX PARTIALS (Selections)
# ============================================

@app.route('/htmx/selections')
def htmx_selections():
    """Alle Selections anzeigen"""
    selections = get_db().execute('SELECT * FROM selections ORDER BY created_at DESC').fetchall()
    return render_template('partials/selections_list.html', selections=selections)


@app.route('/htmx/selection/<int:selection_id>/execute')
def htmx_execute_selection(selection_id):
    """Selection ausführen und Ergebnisse anzeigen"""
    selection = get_db().execute('SELECT * FROM selections WHERE id = ?', (selection_id,)).fetchone()
    if not selection:
        return 'Selection nicht gefunden', 404

    filters = json.loads(selection['filters_json'])
    output_type = selection['output_type']

    if output_type == 'post':
        results = get_posts(filters)
    elif output_type == 'member':
        results = get_members(filters)
    elif output_type == 'community':
        results = get_communities_with_shared_members(filters)
    else:
        results = []

    get_db().execute(
        'UPDATE selections SET result_count = ? WHERE id = ?',
        (len(results), selection_id)
    )
    get_db().commit()

    return render_template('partials/selection_results.html',
        selection=selection,
        results=results[:100],
        total=len(results)
    )


# ============================================
# ROUTES - HTMX PARTIALS (Chat)
# ============================================

@app.route('/htmx/chats')
def htmx_chat_sidebar():
    """Chat-Sidebar"""
    chats = get_db().execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    active_chat = request.args.get('active', type=int)
    return render_template('partials/chat_sidebar.html', chats=chats, active_chat=active_chat)


@app.route('/htmx/chat/<int:chat_id>')
def htmx_chat_messages(chat_id):
    """Chat-Nachrichten laden"""
    database = get_db()
    messages = database.execute(
        'SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at',
        (chat_id,)
    ).fetchall()

    message_ids = [m['id'] for m in messages]
    selections_by_message = {}
    if message_ids:
        placeholders = ','.join(['?' for _ in message_ids])
        selections = database.execute(f'''
            SELECT * FROM selections
            WHERE message_id IN ({placeholders})
            ORDER BY created_at
        ''', message_ids).fetchall()
        for sel in selections:
            mid = sel['message_id']
            if mid not in selections_by_message:
                selections_by_message[mid] = []
            selections_by_message[mid].append(sel)

    return render_template('partials/chat_messages.html',
                          messages=messages,
                          chat_id=chat_id,
                          selections_by_message=selections_by_message)


@app.route('/htmx/chat', methods=['POST'])
def htmx_create_chat():
    """Neuen Chat erstellen"""
    database = get_db()
    cursor = database.execute('INSERT INTO chats (title) VALUES (?)', ('Neuer Chat',))
    database.commit()
    chat_id = cursor.lastrowid

    chats = database.execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()

    response = render_template('partials/chat_sidebar.html', chats=chats, active_chat=chat_id)
    response += f'''
    <div id="chat-main" hx-swap-oob="innerHTML">
        {render_template('partials/chat_messages.html', messages=[], chat_id=chat_id)}
    </div>
    '''
    return response


@app.route('/htmx/chat/<int:chat_id>/delete', methods=['DELETE'])
def htmx_delete_chat(chat_id):
    """Chat löschen"""
    database = get_db()
    database.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    database.commit()

    chats = database.execute(
        'SELECT * FROM chats WHERE archived = 0 ORDER BY updated_at DESC'
    ).fetchall()
    return render_template('partials/chat_sidebar.html', chats=chats)


@app.route('/htmx/chat/<int:chat_id>/message', methods=['POST'])
def htmx_send_message(chat_id):
    """Nachricht senden und AI-Antwort generieren"""
    content = request.form.get('content', '').strip()
    if not content:
        return '', 204

    database = get_db()

    # User-Nachricht speichern
    database.execute(
        'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
        (chat_id, 'user', content)
    )
    database.commit()

    # AI-Antwort generieren
    api_key = get_setting('openai_api_key')
    if not api_key:
        database.execute(
            'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
            (chat_id, 'assistant', 'Bitte OpenAI API Key in Settings konfigurieren.')
        )
        database.commit()
        return htmx_chat_messages(chat_id)

    # Kontext laden
    messages = database.execute(
        'SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at',
        (chat_id,)
    ).fetchall()

    # OpenAI Call
    response = call_openai(api_key, [{'role': m['role'], 'content': m['content']} for m in messages])

    # Selektionen aus der Antwort extrahieren
    clean_response, selections = extract_selections_from_response(response)

    # Assistant-Nachricht speichern
    cursor = database.execute(
        'INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
        (chat_id, 'assistant', clean_response)
    )
    message_id = cursor.lastrowid

    # Selektionen erstellen und mit der Nachricht verknüpfen
    for sel in selections:
        database.execute('''
            INSERT INTO selections (name, output_type, filters_json, created_by, message_id)
            VALUES (?, ?, ?, 'assistant', ?)
        ''', (
            sel.get('name', 'AI-Selektion'),
            sel.get('output_type', 'post'),
            json.dumps(sel.get('filters', {})),
            message_id
        ))

    database.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (datetime.now(), chat_id))
    database.commit()

    return htmx_chat_messages(chat_id)


# ============================================
# OPENAI INTEGRATION
# ============================================

def extract_selections_from_response(response_text):
    """
    Extrahiert Selektionen aus der AI-Antwort.
    Format: [[SELECTION:{"name": "...", "output_type": "...", "filters": {...}}]]
    """
    pattern = r'\[\[SELECTION:(.*?)\]\]'
    selections = []

    for match in re.finditer(pattern, response_text):
        try:
            selection_data = json.loads(match.group(1))
            if 'name' in selection_data and 'output_type' in selection_data:
                selections.append(selection_data)
        except json.JSONDecodeError:
            continue

    clean_text = re.sub(pattern, '', response_text).strip()
    return clean_text, selections


def call_openai(api_key, messages, model='gpt-4o-mini'):
    """Einfacher OpenAI API Call"""
    system_prompt = """Du bist ein hilfreicher Assistent für die Analyse von Skool-Community-Daten.
Du hilfst beim Erstellen von Selektionen, Filtern und Berichten.

WICHTIG: Du kannst Selektionen (Filter) erstellen! Wenn der User nach einem Filter oder einer Selektion fragt,
erstelle eine mit folgendem Format (das JSON muss in einer einzelnen Zeile sein):

[[SELECTION:{"name": "Name der Selektion", "output_type": "post|member|community", "filters": {...}}]]

Verfügbare output_types und ihre Filter:

1. output_type: "post" - Filtert Posts
   Filter: community_ids (list), author_ids (list), likes_min (int), likes_max (int),
   comments_min (int), comments_max (int), date_from (YYYY-MM-DD), date_to (YYYY-MM-DD),
   created_within_days (int), search_text (str), has_content (bool), has_title (bool),
   title_contains (str), content_contains (str), sort (likes|comments|created_at|title), sort_order (ASC|DESC)

2. output_type: "member" - Filtert Mitglieder
   Filter: community_ids (list), roles (list: admin/group-moderator/member/owner), is_owner (bool),
   level_min (int), level_max (int), post_count_min (int), post_count_max (int),
   active_in_last_days (int), inactive_since_days (int), joined_within_days (int),
   bio_contains (str), has_picture (bool), sort (name|level|post_count|joined_at|last_online), sort_order (ASC|DESC)

3. output_type: "community" - Für Community-Vergleiche
   Filter: community_ids (list), member_count_min (int), member_count_max (int),
   post_count_min (int), post_count_max (int), min_shared_members (int)

Beispiel: User fragt "Zeige mir Posts mit mehr als 50 Likes"
Antwort: Hier ist eine Selektion für Posts mit mehr als 50 Likes:
[[SELECTION:{"name": "Posts mit 50+ Likes", "output_type": "post", "filters": {"likes_min": 50, "sort": "likes", "sort_order": "DESC"}}]]

Schreibe IMMER einen kurzen erklärenden Text VOR der Selektion."""

    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system_prompt}] + messages,
        'max_tokens': 2000
    }

    req = Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    try:
        with urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
            data = json.loads(response.read())
            return data['choices'][0]['message']['content']
    except Exception as e:
        return f'Fehler bei OpenAI-Anfrage: {str(e)}'


# ============================================
# MAIN
# ============================================

def open_browser(port):
    webbrowser.open(f'http://localhost:{port}')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='CatKnows Local Server')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Server port')
    parser.add_argument('--no-browser', action='store_true', help='Dont open browser')
    args = parser.parse_args()

    init_db()

    # Default Prompt Templates initialisieren
    with app.app_context():
        init_default_templates()

    # Lizenz pruefen beim Start
    with app.app_context():
        license_status = check_license(get_db())
        if not license_status['has_license']:
            print('[License] Keine Lizenz aktiviert. Bitte im Browser aktivieren.')
        elif not license_status['is_valid']:
            print(f'[License] {license_status["message"]}')
        elif license_status['in_grace_period']:
            print(f'[License] WARNUNG: {license_status["message"]}')
        elif license_status['server_status'] == 'offline':
            print('[License] Server nicht erreichbar - Offline-Modus aktiv')
        else:
            print(f'[License] Gueltig bis {license_status["valid_until"]}')

    print(f'Starting CatKnows on http://localhost:{args.port}')
    print(f'Data directory: {DATA_DIR}')

    if not args.no_browser:
        Timer(0.5, open_browser, [args.port]).start()

    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == '__main__':
    main()

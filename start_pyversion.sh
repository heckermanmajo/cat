#!/bin/bash
# Start CatKnows Python Version

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYVERSION_DIR="$SCRIPT_DIR/pyversion"

cd "$PYVERSION_DIR"

# Aktiviere venv falls vorhanden
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Installiere fehlende Dependencies
pip install -q -r requirements.txt 2>/dev/null

# Starte Flask-App
python app.py "$@"

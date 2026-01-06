#!/bin/bash

# =============================================================================
# Compile Python and Upload to Production Server
# =============================================================================
# Dieses Skript:
# 1. Kompiliert die Python-App mit Nuitka zu einer Binary (catknows)
# 2. Kopiert die Binary in den webserver-Ordner
# 3. Zippt den webserver-Ordner
# 4. Lädt das Zip auf den Produktionsserver hoch
# =============================================================================

set -e  # Bei Fehler abbrechen

SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR="$SCRIPT_DIR/.."

PYVERSION_DIR="$PROJECT_DIR/pyversion"
WEBSERVER_DIR="$PROJECT_DIR/webserver"
BINARY_SOURCE="$PYVERSION_DIR/dist/catknows"

ZIP_FILE_UPLOAD_PATH="/www/htdocs/w016728f/cat-knows.com/"
SSH_SERVER_ADDRESS="ssh-w016728f@w016728f.kasserver.com"

echo "=========================================="
echo "CatKnows Production Deployment"
echo "=========================================="

# -----------------------------------------------------------------------------
# Schritt 1: Python mit Nuitka kompilieren
# -----------------------------------------------------------------------------
echo ""
echo "[1/4] Kompiliere Python mit Nuitka..."
cd "$PYVERSION_DIR"

# Aktiviere venv falls vorhanden
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Build ausführen
python build.py

# Prüfe ob Binary erstellt wurde
if [ ! -f "$BINARY_SOURCE" ]; then
    echo "FEHLER: Binary wurde nicht erstellt: $BINARY_SOURCE"
    exit 1
fi

echo "Binary erstellt: $BINARY_SOURCE"

# -----------------------------------------------------------------------------
# Schritt 2: Binary in webserver-Ordner kopieren
# -----------------------------------------------------------------------------
echo ""
echo "[2/4] Kopiere Binary in webserver-Ordner..."
cp "$BINARY_SOURCE" "$WEBSERVER_DIR/catknows"
chmod +x "$WEBSERVER_DIR/catknows"
echo "Binary kopiert nach: $WEBSERVER_DIR/catknows"

# -----------------------------------------------------------------------------
# Schritt 3: Webserver zippen
# -----------------------------------------------------------------------------
echo ""
echo "[3/4] Erstelle ZIP-Archiv..."
cd "$WEBSERVER_DIR"
zip -r "$PROJECT_DIR/web.zip" ./* -x "*.md" "*excalidraw*"
echo "ZIP erstellt: $PROJECT_DIR/web.zip"

# -----------------------------------------------------------------------------
# Schritt 4: Upload auf Produktionsserver
# -----------------------------------------------------------------------------
echo ""
echo "[4/4] Lade auf Produktionsserver hoch..."
scp "$PROJECT_DIR/web.zip" "$SSH_SERVER_ADDRESS:$ZIP_FILE_UPLOAD_PATH"
ssh "$SSH_SERVER_ADDRESS" "cd $ZIP_FILE_UPLOAD_PATH && unzip -o web.zip && rm web.zip"

# Aufräumen
rm "$PROJECT_DIR/web.zip"

echo ""
echo "=========================================="
echo "Deployment erfolgreich abgeschlossen!"
echo "=========================================="

#!/bin/bash
#
# Start Development Webserver for CatKnows License Server
#
# Usage: ./scripts/start-webserver-dev.sh [port]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEBSERVER_DIR="$PROJECT_DIR/webserver"
PORT="${1:-8080}"

echo "╔════════════════════════════════════════════╗"
echo "║     CatKnows Webserver - Development       ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Check if PHP is installed
if ! command -v php &> /dev/null; then
    echo "❌ PHP ist nicht installiert!"
    echo "   Installiere PHP mit: brew install php"
    exit 1
fi

# Check PHP version
PHP_VERSION=$(php -v | head -n 1 | cut -d " " -f 2 | cut -d "." -f 1,2)
echo "✓ PHP Version: $PHP_VERSION"

# Check for required extensions
echo ""
echo "Prüfe PHP-Extensions..."
php -m | grep -q "pdo" && echo "  ✓ PDO" || echo "  ❌ PDO fehlt"
php -m | grep -q "sodium" && echo "  ✓ Sodium" || echo "  ❌ Sodium fehlt (für Lizenz-Signierung)"
php -m | grep -q "json" && echo "  ✓ JSON" || echo "  ✓ JSON (built-in)"

# Check if port is available
if lsof -i :$PORT &> /dev/null; then
    echo ""
    echo "⚠️  Port $PORT ist bereits belegt!"
    echo "   Beende bestehenden Prozess..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Set development environment variables (falls nicht gesetzt)
export DB_HOST="${DB_HOST:-frellow.de}"
export DB_NAME="${DB_NAME:-d045c2f8}"
export DB_USER="${DB_USER:-d045c2f8}"
export DB_PASS="${DB_PASS:-HJmxWyhNgSJhYXV7Ljiv}"

echo ""
echo "📦 Datenbank-Konfiguration:"
echo "   Host: $DB_HOST"
echo "   Name: $DB_NAME"
echo "   User: $DB_USER"
echo ""

echo "🚀 Starte Server auf http://localhost:$PORT"
echo ""
echo "   📄 Landing Page:  http://localhost:$PORT/"
echo "   🔐 Admin Panel:   http://localhost:$PORT/admin/"
echo "   📥 Download API:  http://localhost:$PORT/api/download.php?info"
echo ""
echo "   Admin-Login: admin / admin123"
echo ""
echo "─────────────────────────────────────────────"
echo "Drücke Ctrl+C zum Beenden"
echo "─────────────────────────────────────────────"
echo ""

# Start PHP built-in server
cd "$WEBSERVER_DIR"
php -S "localhost:$PORT" -t .

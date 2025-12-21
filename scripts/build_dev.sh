#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== CatKnows Dev Build ==="

# 1. Build Frontend
echo "[1/4] Building frontend..."
cd "$PROJECT_ROOT/frontend-client-ui"
npm run build

# 2. Copy frontend to go-client/static
echo "[2/4] Copying frontend assets..."
rm -rf "$PROJECT_ROOT/go-client/static/"*
cp -r "$PROJECT_ROOT/frontend-client-ui/dist/"* "$PROJECT_ROOT/go-client/static/"

# 3. Build Go binary
echo "[3/4] Building Go binary..."
cd "$PROJECT_ROOT/go-client"
go build -o catknows .

# 4. Stop existing server on port 3000
echo "[4/4] Stopping existing server on port 3000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 1

# 5. Start new server (in foreground - Ctrl+C to stop)
echo "Starting catknows server..."
echo "Press Ctrl+C to stop the server"
echo ""
cd "$PROJECT_ROOT/go-client"
exec ./catknows

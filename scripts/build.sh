#!/bin/bash
set -e

echo "=== CatKnows Build ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 1. Frontend bauen
echo ""
echo "[1/3] Building frontend..."
cd frontend-client-ui
npm run build
cd ..

# 2. Frontend-Dist nach Go-Client kopieren
echo ""
echo "[2/3] Copying static files..."
rm -rf go-client/static
cp -r frontend-client-ui/dist go-client/static

# 3. Go Binary bauen
echo ""
echo "[3/3] Building Go binary..."
cd go-client
go build -o ../catknows .
cd ..

echo ""
echo "=== Build complete! ==="
echo "Run with: ./catknows"
echo "Options:"
echo "  --port=8080      Use different port"
echo "  --no-browser     Don't open browser automatically"

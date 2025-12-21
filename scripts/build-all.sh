#!/bin/bash
set -e

echo "=== CatKnows Cross-Platform Build ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Output directory - webserver downloads folder
DOWNLOADS_DIR="$PROJECT_ROOT/webserver/downloads"
mkdir -p "$DOWNLOADS_DIR"

# 1. Frontend bauen (einmalig)
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

# 3. Cross-compile für alle Plattformen
echo ""
echo "[3/3] Building binaries for all platforms..."

cd go-client

# macOS (Apple Silicon)
echo "  - macOS (Apple Silicon)..."
GOOS=darwin GOARCH=arm64 go build -o "$DOWNLOADS_DIR/catknows-macos-arm64" .

# macOS (Intel)
echo "  - macOS (Intel)..."
GOOS=darwin GOARCH=amd64 go build -o "$DOWNLOADS_DIR/catknows-macos-amd64" .

# Windows (64-bit)
echo "  - Windows (64-bit)..."
GOOS=windows GOARCH=amd64 go build -o "$DOWNLOADS_DIR/catknows-windows-amd64.exe" .

# Linux (64-bit)
echo "  - Linux (64-bit)..."
GOOS=linux GOARCH=amd64 go build -o "$DOWNLOADS_DIR/catknows-linux-amd64" .

cd ..

echo ""
echo "=== Build complete! ==="
echo "Binaries in $DOWNLOADS_DIR:"
ls -lh "$DOWNLOADS_DIR/"

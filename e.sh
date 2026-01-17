#!/bin/bash
cd "$(dirname "$0")/electron-fetcher"

# Node modules installieren falls nicht vorhanden
if [ ! -d "node_modules" ]; then
    echo "Installiere dependencies..."
    npm install
fi

# Electron starten (--no-sandbox für Linux ohne root-Sandbox)
./node_modules/.bin/electron . --no-sandbox

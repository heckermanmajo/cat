#!/bin/bash
# Start CatKnows for development (Python server + Electron)

cd "$(dirname "$0")"

# Activate venv if exists
if [ -f "./venv/bin/activate" ]; then
    source ./venv/bin/activate
fi

# Clean up old port file
rm -f .port

# Start Python server in background (from project root, so db is here)
echo "Starting Python server..."
python3 myversion/app.py &
PYTHON_PID=$!

# Wait for port file and server to be ready
echo "Waiting for server..."
for i in {1..30}; do
    if [ -f ".port" ]; then
        PORT=$(cat .port)
        if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
            echo "Server ready on port $PORT!"
            break
        fi
    fi
    sleep 0.5
done

# Start Electron (--no-sandbox for Linux dev)
echo "Starting Electron..."
cd electron-fetcher
npx electron . --no-sandbox
cd ..

# Cleanup: kill Python server when Electron exits
echo "Shutting down..."
kill $PYTHON_PID 2>/dev/null
rm -f .port

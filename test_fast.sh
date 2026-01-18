#!/bin/bash
#
# Fast test runner - runs tests against Python source directly
# Usage: ./test_fast.sh [pytest args]
#
# Examples:
#   ./test_fast.sh                    # Run all tests
#   ./test_fast.sh -v                 # Verbose output
#   ./test_fast.sh -k "role"          # Run only tests with "role" in name
#   ./test_fast.sh tests/test_filter_basic.py  # Run specific test file
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYVERSION_DIR="$SCRIPT_DIR/myversion"
TESTS_DIR="$SCRIPT_DIR/tests"
VENV_DIR="$SCRIPT_DIR/tests/.venv"
PORT=3099
TEST_DB="$MYVERSION_DIR/test_app.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Fast Test Runner ===${NC}"
echo "Running tests against Python source"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    if [ ! -z "$APP_PID" ]; then
        kill $APP_PID 2>/dev/null || true
        wait $APP_PID 2>/dev/null || true
    fi
    rm -f "$TEST_DB"
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install dependencies if needed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -r "$TESTS_DIR/requirements.txt"
    pip install flask flask-cors  # App dependencies
fi

# Remove old test database
rm -f "$TEST_DB"

# Start the Flask app in background
echo -e "${YELLOW}Starting Flask app on port $PORT...${NC}"
cd "$MYVERSION_DIR"

# Use test database
DB_PATH="$TEST_DB" python3 -c "
import sqlite3
from model import Model
Model.connect('test_app.db')
" 2>/dev/null || true

# Start Flask
python3 -c "
import sys
sys.path.insert(0, '.')
from app import app
app.run(port=$PORT, debug=False, threaded=True)
" &
APP_PID=$!

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server...${NC}"
for i in {1..30}; do
    if curl -s "http://localhost:$PORT/api/configentry" > /dev/null 2>&1; then
        echo -e "${GREEN}Server ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Server failed to start${NC}"
        exit 1
    fi
    sleep 0.5
done

# Run tests
echo -e "${YELLOW}Running pytest...${NC}"
cd "$SCRIPT_DIR"
TEST_BASE_URL="http://localhost:$PORT" python3 -m pytest "$TESTS_DIR" "$@"
TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
else
    echo -e "\n${RED}Some tests failed${NC}"
fi

exit $TEST_EXIT_CODE

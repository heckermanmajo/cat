#!/bin/bash
#
# Full test runner - builds executable with Nuitka, then runs tests
# Usage: ./test.sh [pytest args]
#
# Examples:
#   ./test.sh                    # Run all tests
#   ./test.sh -v                 # Verbose output
#   ./test.sh -k "role"          # Run only tests with "role" in name
#   ./test.sh --skip-build       # Skip build, use existing executable
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYVERSION_DIR="$SCRIPT_DIR/myversion"
TESTS_DIR="$SCRIPT_DIR/tests"
DIST_DIR="$MYVERSION_DIR/dist"
BINARY="$DIST_DIR/catknows"
PORT=3098
TEST_DB="$DIST_DIR/test_app.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Full Test Runner (with Nuitka build) ===${NC}"

# Check for --skip-build flag
SKIP_BUILD=false
PYTEST_ARGS=()
for arg in "$@"; do
    if [ "$arg" == "--skip-build" ]; then
        SKIP_BUILD=true
    else
        PYTEST_ARGS+=("$arg")
    fi
done

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

# Install test dependencies if needed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    python3 -m pip install -r "$TESTS_DIR/requirements.txt"
fi

# Build unless skipped
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${YELLOW}Building with Nuitka...${NC}"
    cd "$MYVERSION_DIR"
    python3 build.py

    if [ ! -f "$BINARY" ]; then
        echo -e "${RED}Build failed - binary not found at $BINARY${NC}"
        exit 1
    fi
    echo -e "${GREEN}Build complete: $BINARY${NC}"
else
    echo -e "${YELLOW}Skipping build (--skip-build flag)${NC}"
    if [ ! -f "$BINARY" ]; then
        echo -e "${RED}Binary not found at $BINARY. Run without --skip-build first.${NC}"
        exit 1
    fi
fi

# Remove old test database
rm -f "$TEST_DB"

# Start the executable in background
echo -e "${YELLOW}Starting executable on port $PORT...${NC}"
cd "$DIST_DIR"

# The executable runs in its own directory, using app.db by default
# We'll use a separate test database
$BINARY &
APP_PID=$!

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server...${NC}"
for i in {1..60}; do
    if curl -s "http://localhost:3000/api/configentry" > /dev/null 2>&1; then
        echo -e "${GREEN}Server ready!${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}Server failed to start${NC}"
        exit 1
    fi
    sleep 0.5
done

# Run tests
echo -e "${YELLOW}Running pytest...${NC}"
cd "$SCRIPT_DIR"
TEST_BASE_URL="http://localhost:3000" python3 -m pytest "$TESTS_DIR" "${PYTEST_ARGS[@]}"
TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
else
    echo -e "\n${RED}Some tests failed${NC}"
fi

exit $TEST_EXIT_CODE

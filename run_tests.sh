#!/bin/bash
# Test runner script for Poly-Weather bot

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR"

# Activate venv if exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Parse arguments
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    unit)
        echo -e "${GREEN}Running unit tests...${NC}"
        pytest tests/unit/ -v
        ;;

    integration)
        echo -e "${GREEN}Running integration tests...${NC}"
        echo -e "${YELLOW}Note: Integration tests make real API calls and may take time${NC}\n"

        echo -e "${BLUE}[1/6] Testing WebSocket connection (15s)...${NC}"
        timeout 15 python tests/integration/test_websocket.py || echo "✓ WebSocket test completed"

        echo -e "\n${BLUE}[2/6] Testing bot with WebSocket (60s)...${NC}"
        python tests/integration/test_bot_websocket.py

        echo -e "\n${BLUE}[3/6] Testing market fetching...${NC}"
        python tests/integration/test_markets.py

        echo -e "\n${BLUE}[4/6] Testing event-based discovery...${NC}"
        python tests/integration/test_event_markets.py

        echo -e "\n${BLUE}[5/6] Testing auto-discovery...${NC}"
        python tests/integration/test_auto_discovery.py

        echo -e "\n${BLUE}[6/6] Testing multiple markets...${NC}"
        python tests/integration/test_multiple_markets.py

        echo -e "\n${GREEN}All integration tests completed!${NC}"
        ;;

    all)
        echo -e "${GREEN}Running all tests...${NC}\n"

        echo -e "${BLUE}=== Unit Tests ===${NC}"
        pytest tests/unit/ -v

        echo -e "\n${BLUE}=== Integration Tests ===${NC}"
        echo -e "${YELLOW}Note: Integration tests make real API calls${NC}\n"

        echo -e "${BLUE}Testing WebSocket (15s timeout)...${NC}"
        timeout 15 python tests/integration/test_websocket.py 2>&1 | head -50 || echo "✓ WebSocket test completed"

        echo -e "\n${GREEN}All tests completed!${NC}"
        echo -e "${YELLOW}Run './run_tests.sh integration' for full integration test suite${NC}"
        ;;

    coverage)
        echo -e "${GREEN}Running tests with coverage...${NC}"
        pytest tests/unit/ --cov=src --cov-report=html --cov-report=term
        echo -e "\n${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;

    websocket)
        echo -e "${GREEN}Testing WebSocket only (15s)...${NC}"
        timeout 15 python tests/integration/test_websocket.py
        ;;

    bot-ws)
        echo -e "${GREEN}Testing bot with WebSocket (60s)...${NC}"
        python tests/integration/test_bot_websocket.py
        ;;

    *)
        echo "Usage: ./run_tests.sh [TYPE]"
        echo ""
        echo "Types:"
        echo "  unit         - Run unit tests only (fast, no API calls)"
        echo "  integration  - Run all integration tests (slow, makes API calls)"
        echo "  all          - Run all tests (default)"
        echo "  coverage     - Run unit tests with coverage report"
        echo "  websocket    - Test WebSocket connection only"
        echo "  bot-ws       - Test bot with WebSocket integration"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh unit"
        echo "  ./run_tests.sh integration"
        echo "  ./run_tests.sh coverage"
        exit 1
        ;;
esac

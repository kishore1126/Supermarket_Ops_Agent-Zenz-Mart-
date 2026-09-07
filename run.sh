#!/usr/bin/env bash
# ==============================================================================
# Supermarket Ops Agent (Zenz Mart) — Run Script
# Executes the Telegram Bot agent easily without requiring manual setup.
# Supports both native Python execution and Docker Compose mode.
# ==============================================================================

set -eo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "  🛒 Starting Zenz Mart Supermarket Ops Agent..."
echo "=========================================================="

# 1. Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚠️ .env not found. Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "❌ Error: Missing .env file. Please create one with your TELEGRAM_BOT_TOKEN."
        exit 1
    fi
fi

# 2. Check if Docker mode is explicitly requested via argument
if [ "${1:-}" = "--docker" ]; then
    if ! command -v docker >/dev/null 2>&1; then
        echo "❌ Error: Docker is not installed or not in PATH."
        exit 1
    fi
    echo "🐳 Launching via Docker Compose..."
    exec docker compose up --build
fi

# 3. Detect Python interpreter (python3 or python)
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
elif [ -f "$PROJECT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_CMD="$PROJECT_DIR/.venv/Scripts/python.exe"
elif [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_DIR/.venv/bin/python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "⚠️ Python not found directly in PATH."
    if command -v docker >/dev/null 2>&1; then
        echo "🐳 Falling back to Docker Compose..."
        exec docker compose up --build
    else
        echo "❌ Error: Neither Python nor Docker was found. Please install Python 3.11+ or Docker."
        exit 1
    fi
fi

echo "🐍 Using Python: $($PYTHON_CMD --version)"

# 4. Optional virtual environment setup
if [ -d ".venv" ]; then
    if [ -f ".venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        PYTHON_CMD="python"
    elif [ -f ".venv/Scripts/activate" ]; then
        # shellcheck disable=SC1091
        source .venv/Scripts/activate
        PYTHON_CMD="python"
    fi
fi

# 5. Seed database with initial products, customer balances, and Zenz Mart preferences if needed
echo "🌱 Checking and initializing database..."
$PYTHON_CMD -m app.scripts.seed

# 6. Start the Telegram Bot Application
echo "🚀 Launching Zenz Mart Telegram Bot..."
echo "👉 Press Ctrl+C anytime to stop."
echo "----------------------------------------------------------"
exec $PYTHON_CMD -m app.main
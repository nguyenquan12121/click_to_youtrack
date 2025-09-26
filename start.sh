#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV=".venv"
PYTHON_CMD="python3"

if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "Error: $PYTHON_CMD is not installed or not in PATH" >&2
    exit 1
fi

if [ ! -f "$VENV/bin/python" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV"
    echo "Virtual environment created successfully"
fi

PY="$VENV/bin/python"

echo "Upgrading pip..."
"$PY" -m pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    "$PY" -m pip install -r "requirements.txt"
    echo "Dependencies installed successfully"
fi

echo "Starting YouTrack-GitHub Sync application..."
"$PY" "src/app.py"
#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Setting up Health Metrics..."

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required. Install it from https://www.python.org or via Homebrew: brew install python"
    exit 1
fi

# Create virtualenv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Install dependencies
echo "Installing dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# Create .env if missing
if [ ! -f ".env" ]; then
    echo ""
    echo "An Oura Personal Access Token is required."
    echo "Get one at: https://cloud.ouraring.com/personal-access-tokens"
    echo ""
    read -p "Oura Personal Access Token: " oura_pat
    cat > .env <<EOF
OURA_PAT=$oura_pat
EOF
    echo ".env created."
fi

# Make launcher executable
chmod +x "Health Metrics.command"

echo ""
echo "Setup complete! Double-click 'Health Metrics.command' in Finder to launch the app."

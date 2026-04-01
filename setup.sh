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
    echo "Oura API credentials are required."
    echo "Get them at: https://cloud.ouraring.com/oauth/applications"
    echo ""
    read -p "Oura Client ID: " client_id
    read -p "Oura Client Secret: " client_secret
    cat > .env <<EOF
OURA_CLIENT_ID=$client_id
OURA_CLIENT_SECRET=$client_secret
OURA_REDIRECT_URI=http://localhost:8501/oauth/callback
EOF
    echo ".env created."
fi

# Make launcher executable
chmod +x "Health Metrics.command"

echo ""
echo "Setup complete! Double-click 'Health Metrics.command' in Finder to launch the app."

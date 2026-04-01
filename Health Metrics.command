#!/bin/bash
# Double-click this file in Finder to launch Health Metrics.
# On first run it will open Terminal to complete setup.

cd "$(dirname "$0")"

# First-time setup
if [ ! -d ".venv" ] || [ ! -f ".env" ]; then
    echo "Running first-time setup..."
    bash setup.sh
    echo ""
fi

echo "Starting Health Metrics..."
.venv/bin/streamlit run app.py

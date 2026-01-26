#!/bin/bash

start_agents() {
    # Function to handle the cleanup
    cleanup() {
        echo -e "\n\nShutting down processes..."
        # Kill all background processes started by this script
        # Check if jobs exist to avoid error messages if none are running
        if [ -n "$(jobs -p)" ]; then
            kill $(jobs -p)
        fi
        echo "Done."
        exit
    }

    # Trap the SIGINT signal (Ctrl+C) and call the cleanup function
    trap cleanup SIGINT

    echo "Starting ADK API Server and Web interface..."

    # Start the API Server in the background
    adk api_server --a2a --port 8001 sequential_agent/remote_a2a &

    # Start the Web interface in the background
    adk web . &

    # Wait for background processes to finish (keeps the script alive)
    wait
}

# --- Check for the internal flag (Recursive Entry Point) ---
if [ "$1" == "--internal-run" ]; then
    # We are now inside the aws-vault session
    start_agents
    exit 0
fi

# --- Main Script Entry Point ---

# Check if an argument was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <AWS PROFILE NAME>"
    echo "Example: $0 eligibility-staging"
    exit 1
fi

# Assign the first argument to a variable
ENVIRONMENT=$1

# Check if the .venv directory/file exists and if a venv is NOT already active.
if [ -d ".venv" ] || [ -f ".venv" ]; then
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Found .venv. Sourcing..."
        source .venv/bin/activate 2>/dev/null || source .venv
    else
        echo "Venv already active, skipping source."
    fi
else
    echo "No .venv found in current directory."
fi

# Check if uv is already installed and install if not
if command -v uv &> /dev/null; then
    echo "✅ uv is already installed at $(which uv)."
else
    # Install uv using pip (using --user to avoid permission issues)
    echo "Installing uv via pip..."
    if pip install --user uv; then
        echo "✅ uv installed successfully!"
        
        # Check if the user bin directory is in PATH (common issue with --user installs)
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo "⚠️  Note: You may need to add '$HOME/.local/bin' to your PATH to run uv."
        fi
    else
        echo "❌ Failed to install uv."
        exit 1
    fi
fi

uv sync

# --- Login to AWS and run this script recursively ---
# We pass "$0" (this script's path) and the internal flag
echo "Launching agents inside aws-vault session..."
aws-vault exec "$ENVIRONMENT" -- "$0" --internal-run
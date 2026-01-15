#!/bin/bash

# Function to handle the cleanup
cleanup() {
    echo -e "\n\nShutting down processes..."
    # Kill all background processes started by this script
    kill $(jobs -p)
    echo "Done."
    exit
}

# Trap the SIGINT signal (Ctrl+C) and call the cleanup function
trap cleanup SIGINT

echo "Starting ADK API Server and Web interface..."

# 1. Start the API Server in the background
adk api_server --a2a --port 8001 sequential_agent/remote_a2a &

# 2. Start the Web interface in the background
adk web . &

# Wait for background processes to finish (keeps the script alive)
wait
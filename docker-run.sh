#!/bin/bash

# Multi-Agentic Drone Simulation - Docker Runner Script
# This script handles X11 forwarding setup and runs the simulation

set -e

echo "🚁 Multi-Agentic Drone Simulation - Docker Setup"
echo "================================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file with your OpenAI API key before running!"
    echo "   You can get an API key from: https://platform.openai.com/api-keys"
    exit 1
fi

# Create necessary directories with proper permissions
mkdir -p logs data docker-home
chmod 777 logs data docker-home
# Ensure the current user owns the directories
chown -R $(id -u):$(id -g) logs data docker-home 2>/dev/null || true

# Create runtime directories for audio/graphics
mkdir -p /tmp/runtime-$(id -u) 2>/dev/null || true
chmod 700 /tmp/runtime-$(id -u) 2>/dev/null || true

# Set up X11 forwarding permissions
echo "🔧 Setting up X11 forwarding for visualization..."
xhost +local:docker > /dev/null 2>&1 || echo "⚠️  Could not set X11 permissions (xhost not available)"

# Get current user ID and group ID for proper file permissions
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

# Check if running with or without visualization
if [ "$1" = "--headless" ]; then
    echo "🖥️  Running in headless mode (no visualization)"
    docker compose --profile headless up drone-simulation-headless
else
    echo "🎮 Running with visualization enabled"
    echo "   Make sure you have X11 forwarding enabled!"
    docker compose up drone-simulation
fi

echo "🏁 Simulation completed!"

#!/bin/bash
# AuroraVRS - Automated VPS Deployment Script
# Targeted for Ubuntu 22.04+ (Contabo VPS)

set -e

echo "--- 🚀 Starting AuroraVRS Deployment ---"

# 1. Update System
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker
if ! [ -x "$(command -v docker)" ]; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "Docker installed successfully."
else
    echo "Docker is already installed."
fi

# 3. Install Docker Compose
if ! [ -x "$(command -v docker compose)" ]; then
    echo "Installing Docker Compose..."
    sudo apt-get install -y docker-compose-plugin
    echo "Docker Compose installed successfully."
else
    echo "Docker Compose is already installed."
fi

# 4. Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found! Please create one based on .env_example."
    # Optional: read from existing .env if present during script generation
else
    echo ".env file detected."
fi

# 5. Build and Start Containers
echo "Building and starting Docker containers..."
sudo docker compose up -d --build

echo "--- ✅ Deployment Complete! ---"
echo "You can check the logs with: docker compose logs -f"

#!/bin/bash
# DroneSync deployment script for server 128.140.52.200

set -e

echo "=== DroneSync Deploy ==="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi

if ! command -v docker compose &> /dev/null; then
    echo "Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Build images
echo "Building images..."
docker compose build

# Stop old containers
echo "Stopping old containers..."
docker compose down || true

# Start all services
echo "Starting services..."
docker compose up -d

# Show status
echo ""
echo "=== Status ==="
docker compose ps

echo ""
echo "=== Logs (last 20 lines) ==="
docker compose logs --tail=20

echo ""
echo "DroneSync running on:"
echo "  Miner:     http://$(hostname -I | awk '{print $1}'):8080"
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):8888"

#!/bin/bash

set -e

echo "🚀 Starting Companion API..."

# Start all services
docker compose up -d --build

echo "⏳ Waiting for services..."

# Wait for Ollama to be healthy
until docker compose exec ollama curl -f http://localhost:11434/api/tags >/dev/null 2>&1; do
    sleep 1
done

# echo "📥 Pulling Ollama model (gemma3)..."
# docker compose exec ollama ollama pull gemma3

echo "✅ All services ready!"
echo ""
echo "📊 Access points:"
echo "  - API: http://localhost:8010"
echo "  - Docs: http://localhost:8010/docs"
echo "  - Flower: http://localhost:5557"
echo "  - Ollama: http://localhost:11434"
echo ""
echo "🔍 View logs: docker compose logs -f"

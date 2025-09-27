#!/bin/bash

# Migration helper script
# Usage: ./migrate.sh "migration message"

if [ -z "$1" ]; then
    echo "❌ Error: Migration message required"
    echo "Usage: ./migrate.sh \"your migration message\""
    exit 1
fi

MESSAGE="$1"

echo "�� Creating migration: $MESSAGE"
docker-compose exec web alembic revision --autogenerate -m "$MESSAGE"

echo "🚀 Applying migration..."
docker-compose exec web alembic upgrade head

echo "✅ Migration complete: $MESSAGE"

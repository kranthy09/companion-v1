#!/bin/bash

# FastAPI postgres db reset script
# This script removes the existing db, migrations, and migrate existing models.

echo "🗑️  Resetting database and migrations..."

# Stop containers
docker compose down

# Remove database volume (this deletes all data)
docker volume rm $(docker compose config --volumes | grep companion)

# Remove all migration files except __pycache__
rm -rf alembic/versions/*.py
rm -rf alembic/versions/__pycache__

# Recreate initial migration
echo "📝 Creating fresh migration..."
docker compose up -d --build
sleep 10  # Wait for DB to be ready

# Generate new migration with all models
docker compose exec web alembic revision --autogenerate -m "Fresh migration Auth, User, Notes models"

# Apply migration
docker compose exec web alembic upgrade head

echo "✅ Database reset complete!"
echo "🚀 Starting services..."
docker-compose up --build
#!/bin/bash

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if migration message provided
if [ -z "$1" ]; then
    log_error "Migration message required"
    echo "Usage: ./migrate.sh \"Your migration message\""
    exit 1
fi

MIGRATION_MESSAGE="$1"

log_info "Starting migration process..."

# Start containers
log_info "Starting Docker containers..."
docker compose up -d

# Wait for DB
log_info "Waiting for database to be ready..."
sleep 10

# Check DB connection
log_info "Checking database connection..."
if docker compose exec web python -c "from project.database import engine; engine.connect()" 2>/dev/null; then
    log_success "Database connected"
else
    log_error "Database connection failed"
    docker compose logs db
    exit 1
fi

# Generate migration
log_info "Generating migration: $MIGRATION_MESSAGE"
docker compose exec web alembic revision --autogenerate -m "$MIGRATION_MESSAGE"

# Apply migration
log_info "Applying migration..."
docker compose exec web alembic upgrade head

# Verify
log_info "Verifying migration..."
docker compose exec web alembic current

# Restart services
log_info "Restarting services..."
docker compose restart web celery_worker celery_beat

log_success "Migration completed successfully!"
log_info "Current migration:"
docker compose exec web alembic current
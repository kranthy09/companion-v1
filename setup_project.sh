#!/bin/bash

# FastAPI-Celery Automated Project Setup Script
# This script reads configuration from project.config and sets up everything automatically

set -e

CONFIG_FILE="project.config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Configuration file '$CONFIG_FILE' not found!"
    log_info "Please create $CONFIG_FILE with your project settings."
    exit 1
fi

# Load configuration
log_info "Loading configuration from $CONFIG_FILE..."
source "$CONFIG_FILE"

# Validate required variables
required_vars=(
    "PROJECT_NAME" "PROJECT_TITLE" "DB_NAME" "DB_USER" "DB_PASSWORD"
    "CONTAINER_PREFIX" "API_HOST_PORT" "FLOWER_HOST_PORT"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        log_error "Required variable $var is not set in $CONFIG_FILE"
        exit 1
    fi
done

# Display configuration
log_warning "⚠️  THIS SCRIPT WILL MODIFY YOUR PROJECT FILES ⚠️"
echo "=================================="
echo "Project: $PROJECT_NAME"
echo "Database: $DB_NAME"
echo "Container Prefix: $CONTAINER_PREFIX"
echo "API Port: $API_HOST_PORT"
echo "Flower Port: $FLOWER_HOST_PORT"
echo "=================================="
echo ""

# First confirmation
read -p "$(echo -e ${YELLOW}Are you sure you want to continue? \(Y/N\): ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Setup cancelled."
    exit 0
fi

# Second confirmation
read -p "$(echo -e ${RED}This will overwrite existing files. Confirm again? \(Y/N\): ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Setup cancelled."
    exit 0
fi

log_info "🚀 Starting automated project setup for: $PROJECT_NAME"

# Create backups
log_info "📁 Creating backups..."
backup_files=(
    "docker-compose.yml"
    "docker-compose.prod.yml"
    ".env/.dev-sample"
    ".env/.prod-sample"
    "main.py"
    "project/config.py"
)

for file in "${backup_files[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$file.bak"
        log_success "Backed up $file"
    fi
done

# Function to replace text in files
replace_in_file() {
    local file="$1"
    local search="$2"
    local replace="$3"

    if [ -f "$file" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|${search}|${replace}|g" "$file"
        else
            sed -i "s|${search}|${replace}|g" "$file"
        fi
    fi
}

# Update docker-compose.yml
log_info "🐳 Updating docker-compose.yml..."
replace_in_file "docker-compose.yml" "fastapi_celery_example_web" "${CONTAINER_PREFIX}_web"
replace_in_file "docker-compose.yml" "fastapi_celery_example_celery_worker" "${CONTAINER_PREFIX}_celery_worker"
replace_in_file "docker-compose.yml" "fastapi_celery_example_celery_beat" "${CONTAINER_PREFIX}_celery_beat"
replace_in_file "docker-compose.yml" "fastapi_celery_example_celery_flower" "${CONTAINER_PREFIX}_celery_flower"
replace_in_file "docker-compose.yml" "8010:8000" "${API_HOST_PORT}:8000"
replace_in_file "docker-compose.yml" "5557:5555" "${FLOWER_HOST_PORT}:5555"
replace_in_file "docker-compose.yml" "POSTGRES_DB=fastapi_celery" "POSTGRES_DB=${DB_NAME}"
replace_in_file "docker-compose.yml" "POSTGRES_USER=fastapi_celery" "POSTGRES_USER=${DB_USER}"
replace_in_file "docker-compose.yml" "POSTGRES_PASSWORD=fastapi_celery" "POSTGRES_PASSWORD=${DB_PASSWORD}"

# Update production docker-compose
if [ -f "docker-compose.prod.yml" ]; then
    log_info "🐳 Updating docker-compose.prod.yml..."
    replace_in_file "docker-compose.prod.yml" "fastapi_celery_example_web" "${CONTAINER_PREFIX}_web"
    replace_in_file "docker-compose.prod.yml" "fastapi_celery_example_celery_worker" "${CONTAINER_PREFIX}_celery_worker"
    replace_in_file "docker-compose.prod.yml" "fastapi_celery_example_celery_beat" "${CONTAINER_PREFIX}_celery_beat"
    replace_in_file "docker-compose.prod.yml" "fastapi_celery_example_celery_flower" "${CONTAINER_PREFIX}_celery_flower"
    replace_in_file "docker-compose.prod.yml" "POSTGRES_DB=fastapi_celery" "POSTGRES_DB=${DB_NAME}"
    replace_in_file "docker-compose.prod.yml" "POSTGRES_USER=fastapi_celery" "POSTGRES_USER=${DB_USER}"
    replace_in_file "docker-compose.prod.yml" "POSTGRES_PASSWORD=fastapi_celery" "POSTGRES_PASSWORD=${DB_PASSWORD}"
fi

# Update environment files
log_info "🔧 Updating environment files..."
db_url="postgresql://${DB_USER}:${DB_PASSWORD}@db/${DB_NAME}"
replace_in_file ".env/.dev-sample" "postgresql://fastapi_celery:fastapi_celery@db/fastapi_celery" "$db_url"

if [ -f ".env/.prod-sample" ]; then
    replace_in_file ".env/.prod-sample" "postgresql://fastapi_celery:fastapi_celery@db/fastapi_celery" "$db_url"
    replace_in_file ".env/.prod-sample" "RABBITMQ_DEFAULT_USER=admin" "RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}"
    replace_in_file ".env/.prod-sample" "RABBITMQ_DEFAULT_PASS=admin" "RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}"
    replace_in_file ".env/.prod-sample" "CELERY_FLOWER_USER=admin" "CELERY_FLOWER_USER=${FLOWER_USER}"
    replace_in_file ".env/.prod-sample" "CELERY_FLOWER_PASSWORD=admin" "CELERY_FLOWER_PASSWORD=${FLOWER_PASSWORD}"
fi

# Update main.py
log_info "📝 Updating main.py..."
cat > main.py << EOF
from project import create_app

app = create_app()
celery = app.celery_app

# Project metadata
app.title = "${PROJECT_TITLE}"
app.description = "${PROJECT_DESCRIPTION}"
app.version = "${PROJECT_VERSION}"

# Additional metadata
app.contact = {
    "name": "${PROJECT_NAME}",
    "url": "https://example.com/contact/",
    "email": "contact@example.com",
}

app.license_info = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT",
}
EOF

# Update config.py
log_info "⚙️ Updating project/config.py..."
if [ -f "project/config.py" ]; then
    replace_in_file "project/config.py" "f\"sqlite:///{BASE_DIR}/db.sqlite3\"" "f\"sqlite:///{BASE_DIR}/${PROJECT_NAME}.sqlite3\""
fi

# Rename domain module if specified
if [ -n "$DOMAIN_MODULE" ] && [ "$DOMAIN_MODULE" != "users" ]; then
    if [ -d "project/users" ]; then
        log_info "🔄 Renaming users module to $DOMAIN_MODULE..."
        mv "project/users" "project/$DOMAIN_MODULE"

        # Update imports in __init__.py
        replace_in_file "project/__init__.py" "from project.users import users_router" "from project.$DOMAIN_MODULE import ${DOMAIN_MODULE}_router"
        replace_in_file "project/__init__.py" "app.include_router(users_router)" "app.include_router(${DOMAIN_MODULE}_router)"

        # Update router definition in the module
        replace_in_file "project/$DOMAIN_MODULE/__init__.py" "users_router = APIRouter(" "${DOMAIN_MODULE}_router = APIRouter("
        replace_in_file "project/$DOMAIN_MODULE/__init__.py" 'prefix="/users"' "prefix=\"/$DOMAIN_MODULE\""

        log_success "Renamed users module to $DOMAIN_MODULE"
    fi
fi

# Create environment file
log_info "📄 Creating .env/.dev file..."
cp .env/.dev-sample .env/.dev

# Make scripts executable
log_info "🔐 Making scripts executable..."
find compose/ -name "start" -o -name "entrypoint" | xargs chmod +x

# Create .env file for docker-compose variable substitution
log_info "📄 Creating .env file for Docker Compose..."
cat > .env << EOF
# Docker Compose Environment Variables
CONTAINER_PREFIX=${CONTAINER_PREFIX}
API_HOST_PORT=${API_HOST_PORT}
FLOWER_HOST_PORT=${FLOWER_HOST_PORT}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
EOF

# Update README.md
log_info "📚 Creating project README..."
cat > README.md << EOF
# ${PROJECT_NAME}

${PROJECT_DESCRIPTION}

## Quick Start

\`\`\`bash
# Clone and setup
git clone <your-repo-url> ${PROJECT_NAME}
cd ${PROJECT_NAME}

# Configure your project
# Edit project.config with your settings
./setup_project.sh

# Start the application
docker compose up --build
\`\`\`

## Access Points

- **API**: http://localhost:${API_HOST_PORT}
- **API Documentation**: http://localhost:${API_HOST_PORT}/docs
- **Interactive API**: http://localhost:${API_HOST_PORT}/redoc
- **Flower (Celery Monitor)**: http://localhost:${FLOWER_HOST_PORT}

## Project Structure

- **FastAPI** web framework with async support
- **Celery** for background task processing
- **PostgreSQL** database with SQLAlchemy ORM
- **Redis** message broker (development)
- **RabbitMQ** message broker (production)
- **WebSocket** support for real-time updates
- **Docker** containerization

## Development Commands

\`\`\`bash
# View logs
docker compose logs -f

# Access web container
docker compose exec web bash

# Run database migrations
docker compose exec web alembic upgrade head

# Create new migration
docker compose exec web alembic revision --autogenerate -m "Description"

# Run tests (if available)
docker compose exec web pytest

# Stop services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
\`\`\`

## Configuration

All project configuration is managed through:
- \`project.config\` - Main project settings
- \`.env/.dev\` - Development environment variables
- \`.env/.prod\` - Production environment variables (create manually)

## Database

- **Development**: PostgreSQL in Docker container
- **Connection**: postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${POSTGRES_HOST_PORT}/${DB_NAME}

## Background Tasks

Celery tasks are processed asynchronously. Monitor them through:
- Flower dashboard: http://localhost:${FLOWER_HOST_PORT}
- Logs: \`docker compose logs celery_worker\`

## Production Deployment

\`\`\`bash
# Use production configuration
docker compose -f docker-compose.prod.yml up --build
\`\`\`

## API Documentation

FastAPI automatically generates OpenAPI documentation:
- Swagger UI: http://localhost:${API_HOST_PORT}/docs
- ReDoc: http://localhost:${API_HOST_PORT}/redoc
- OpenAPI JSON: http://localhost:${API_HOST_PORT}/openapi.json
EOF

# Initialize git if requested
if [ -n "$GIT_REMOTE_URL" ]; then
    log_info "🔧 Setting up git repository..."
    git init
    git add .
    git commit -m "Initial commit: Setup ${PROJECT_NAME} from FastAPI-Celery template"
    git branch -M "$GIT_BRANCH"
    git remote add origin "$GIT_REMOTE_URL"
    log_success "Git repository initialized with remote: $GIT_REMOTE_URL"
fi

# Create project info file
cat > project_info.txt << EOF
Project Setup Complete: $(date)
==============================
Project Name: ${PROJECT_NAME}
Database: ${DB_NAME}
Container Prefix: ${CONTAINER_PREFIX}
API Port: ${API_HOST_PORT}
Flower Port: ${FLOWER_HOST_PORT}

Access Points:
- API: http://localhost:${API_HOST_PORT}
- Docs: http://localhost:${API_HOST_PORT}/docs
- Flower: http://localhost:${FLOWER_HOST_PORT}

Next Steps:
1. docker compose up --build
2. Visit http://localhost:${API_HOST_PORT}/docs
3. Customize your domain models in project/${DOMAIN_MODULE:-users}/

Configuration stored in:
- project.config (main settings)
- .env (docker-compose variables)
- .env/.dev (application environment)
EOF

echo ""
log_success "🎉 Project setup completed successfully!"
echo ""
log_info "📋 Next steps:"
echo "   1. Review the configuration in project_info.txt"
echo "   2. Start the application: docker compose up --build"
echo "   3. Visit: http://localhost:${API_HOST_PORT}"
echo "   4. API Documentation: http://localhost:${API_HOST_PORT}/docs"
echo "   5. Flower Dashboard: http://localhost:${FLOWER_HOST_PORT}"
echo ""
log_info "📁 Backup files created (*.bak) - you can remove them later"
log_info "🗃️  Project info saved in: project_info.txt"
echo ""
log_warning "Don't forget to customize your domain models and business logic!"
# fastapi-celery-project

## Commands(local development)

```bash
docker run -p 6379:6379 --name some-redis -d redis
```

```bash
uvicorn main:app --reload
```

```bash
celery -A main.celery worker --loglevel=info
```

```bash
celery -A main.celery flower --port=5555
```

## Retry Failed Tasks:

### 1. Task Retry Decorator

```python
@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 7, "countdown": 5})
def task_process_notification(self):
if not random.choice([0, 1]): # mimic random error
raise Exception()

    requests.post("https://httpbin.org/delay/5")
```

- autoretry_for takes a list/tuple of exception types that you'd like to retry for.
- retry_kwargs takes a dictionary of additional options for specifying how autoretries
  are executed. In the above example, the task will retry after a 5 second delay (via countdown)
  and it allows for a maximum of 7 retry attempts (via max_retries). Celery will stop
  retrying after 7 failed attempts and raise an exception.

### 2. Exponential Backoff

If your Celery task needs to send a request to a third-party service, it's a good idea to use exponential backoff to avoid overwhelming the service.

Celery supports this by default:

```python
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def task_process_notification(self):
    if not random.choice([0, 1]):
        # mimic random error
        raise Exception()

    requests.post("https://httpbin.org/delay/5")
```

You can also set retry_backoff to a number for use as a delay factor

To prevent thundering herd, celery has you covere here with `retry_jitter`. This option is set `true` by default to prevent thundering herd problem when you use celery's built-in `retry_backoff`

## pytest

```bash
docker compose up -d --build
```

Run Tests:

```bash
docker compose exec web pytest
```

Coverage:

```bash
 docker compose exec web pytest --cov=.
```

HTML Report(test):

```bash
docker compose exec web pytest --cov=. --cov-report html
```

# FastAPI-Celery Project Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Project Structure](#project-structure)
5. [Core Components](#core-components)
6. [Development Workflow](#development-workflow)
7. [Adding New Features](#adding-new-features)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

## Project Overview

This is a FastAPI application with Celery for asynchronous task processing, featuring:

- **FastAPI** web framework for REST APIs
- **Celery** for background task processing
- **Redis** as message broker (dev) / **RabbitMQ** (prod)
- **PostgreSQL** database
- **WebSocket** support for real-time updates
- **Socket.IO** for bidirectional communication
- **Flower** for Celery monitoring
- **Docker Compose** for containerization
- **Alembic** for database migrations

## Architecture

### Development Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis    │◀────│   Celery    │
│   (web)     │     │   (broker)  │     │  (worker)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐                        ┌─────────────┐
│ PostgreSQL  │                        │   Flower    │
│    (db)     │                        │ (monitoring)│
└─────────────┘                        └─────────────┘
```

### Production Architecture

```
┌─────────────┐
│    Nginx    │ (Reverse Proxy - ports 80, 5559, 15672)
└─────────────┘
       │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│  RabbitMQ   │◀────│   Celery    │
│   (web)     │     │   (broker)  │     │  (worker)   │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

### Local Development Setup

1. **Clone the repository**

```bash
git clone <repository-url>
cd fastapi-celery-project
```

2. **Set up environment variables**

```bash
cp .env/.dev-sample .env/.dev
# Edit .env/.dev as needed
```

3. **Start services with Docker Compose**

```bash
docker-compose up --build
```

4. **Access the services**

- FastAPI: http://localhost:8010
- API Docs: http://localhost:8010/docs
- Flower: http://localhost:5557

### Without Docker (Local Python)

1. **Start Redis**

```bash
docker run -p 6379:6379 --name some-redis -d redis
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Run database migrations**

```bash
alembic upgrade head
```

4. **Start FastAPI**

```bash
uvicorn main:app --reload
```

5. **Start Celery worker**

```bash
celery -A main.celery worker --loglevel=info
```

6. **Start Flower (optional)**

```bash
celery -A main.celery flower --port=5555
```

## Project Structure

```
fastapi-celery-project/
├── project/                    # Main application package
│   ├── __init__.py            # App factory and initialization
│   ├── config.py              # Configuration settings
│   ├── database.py            # Database setup and session management
│   ├── celery_utils.py        # Celery configuration helpers
│   ├── logging.py             # Logging configuration
│   ├── users/                 # Users module
│   │   ├── __init__.py        # Router initialization
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── tasks.py           # Celery tasks
│   │   ├── views.py           # API endpoints
│   │   └── templates/         # HTML templates
│   └── ws/                    # WebSocket module
│       ├── __init__.py
│       └── views.py           # WebSocket endpoints
├── alembic/                   # Database migrations
│   ├── versions/              # Migration files
│   └── env.py                 # Alembic configuration
├── compose/                   # Docker configurations
│   ├── local/                 # Development Docker files
│   └── production/            # Production Docker files
├── main.py                    # Application entry point
├── docker-compose.yml         # Development compose file
├── docker-compose.prod.yml    # Production compose file
└── requirements.txt           # Python dependencies
```

## Core Components

### 1. FastAPI Application (`project/__init__.py`)

The application factory pattern creates and configures the FastAPI app:

```python
def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # Configure logging
    configure_logging()

    # Initialize Celery
    app.celery_app = create_celery()

    # Register routers
    app.include_router(users_router)
    app.include_router(ws_router)

    # Register Socket.IO
    register_socketio_app(app)

    return app
```

### 2. Celery Tasks (`project/users/tasks.py`)

Key task patterns:

**Basic Task:**

```python
@shared_task
def sample_task(email):
    api_call(email)
```

**Task with Retry Logic:**

```python
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 7, "countdown": 5}
)
def task_process_notification(self):
    # Task implementation
```

**Task with Database Access:**

```python
@shared_task()
def task_send_welcome_email(user_pk):
    with db_context() as session:
        user = session.get(User, user_pk)
        # Send email logic
```

### 3. WebSocket Integration (`project/ws/views.py`)

Real-time task status updates via WebSocket:

```python
@ws_router.websocket("/ws/task_status/{task_id}")
async def ws_task_status(websocket: WebSocket):
    await websocket.accept()
    task_id = websocket.scope["path_params"]["task_id"]
    # Broadcast task updates
```

### 4. Database Models (`project/users/models.py`)

SQLAlchemy models with Alembic migrations:

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(128), unique=True, nullable=False)
    email = Column(String(128), unique=True, nullable=False)
```

## Development Workflow

### 1. Creating a New Feature Module

Create a new module structure:

```bash
project/
└── your_feature/
    ├── __init__.py      # Router setup
    ├── models.py        # Database models
    ├── schemas.py       # Pydantic models
    ├── tasks.py         # Celery tasks
    └── views.py         # API endpoints
```

### 2. Database Migrations

After modifying models:

```bash
# Generate migration
docker-compose exec web alembic revision --autogenerate -m "Add new feature"

# Apply migration
docker-compose exec web alembic upgrade head
```

### 3. Adding Celery Tasks

**Step 1:** Define task in `tasks.py`:

```python
@shared_task
def your_async_task(param1, param2):
    # Task logic
    return result
```

**Step 2:** Call task from view:

```python
@router.post("/trigger-task/")
def trigger_task(data: YourSchema):
    task = your_async_task.delay(data.param1, data.param2)
    return {"task_id": task.id}
```

### 4. Task Queue Routing

Configure task routing in `project/config.py`:

```python
CELERY_TASK_ROUTES = {
    "project.your_feature.tasks.*": {
        "queue": "high_priority",
    },
}
```

Or use dynamic routing:

```python
@shared_task(name="high_priority:critical_task")
def critical_task():
    # Will route to high_priority queue
```

## Adding New Features

### Example: Adding a Blog Module

1. **Create module structure:**

```bash
mkdir -p project/blog
touch project/blog/{__init__.py,models.py,schemas.py,tasks.py,views.py}
```

2. **Define router** (`project/blog/__init__.py`):

```python
from fastapi import APIRouter

blog_router = APIRouter(prefix="/blog")

from . import views, models, tasks
```

3. **Create model** (`project/blog/models.py`):

```python
from sqlalchemy import Column, Integer, String, Text, DateTime
from project.database import Base
from datetime import datetime

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

4. **Define schemas** (`project/blog/schemas.py`):

```python
from pydantic import BaseModel
from datetime import datetime

class BlogPostCreate(BaseModel):
    title: str
    content: str

class BlogPostResponse(BlogPostCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

5. **Add endpoints** (`project/blog/views.py`):

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from . import blog_router
from .models import BlogPost
from .schemas import BlogPostCreate, BlogPostResponse
from project.database import get_db_session

@blog_router.post("/", response_model=BlogPostResponse)
def create_post(
    post: BlogPostCreate,
    db: Session = Depends(get_db_session)
):
    db_post = BlogPost(**post.dict())
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post
```

6. **Register router** in `project/__init__.py`:

```python
from project.blog import blog_router
app.include_router(blog_router)
```

7. **Run migration:**

```bash
docker-compose exec web alembic revision --autogenerate -m "Add blog posts"
docker-compose exec web alembic upgrade head
```

## Testing

### Manual Testing

1. **API Testing:**

   - Use FastAPI's auto-generated docs at `/docs`
   - Test WebSocket connections at `/users/form_ws/`
   - Test Socket.IO at `/users/form_socketio/`

2. **Celery Testing:**
   - Monitor tasks in Flower dashboard
   - Check task status via API: `/users/task_status/?task_id=xxx`

### Unit Testing (To be implemented)

```python
# tests/test_users.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_user():
    response = client.post(
        "/users/form/",
        json={"username": "test", "email": "test@example.com"}
    )
    assert response.status_code == 200
    assert "task_id" in response.json()
```

## Deployment

### Production Deployment to DigitalOcean

1. **Set environment variables:**

```bash
export DIGITAL_OCEAN_ACCESS_TOKEN=your_token
export DIGITAL_OCEAN_IP_ADDRESS=your_server_ip
```

2. **Deploy:**

```bash
bash compose/auto_deploy_do.sh
```

### Environment Variables

**Development** (`.env/.dev-sample`):

```
FASTAPI_CONFIG=development
DATABASE_URL=postgresql://fastapi_celery:fastapi_celery@db/fastapi_celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
WS_MESSAGE_QUEUE=redis://redis:6379/0
```

**Production** (`.env/.prod-sample`):

```
FASTAPI_CONFIG=production
DATABASE_URL=postgresql://fastapi_celery:fastapi_celery@db/fastapi_celery
CELERY_BROKER_URL=amqp://admin:admin@rabbitmq:5672/
CELERY_RESULT_BACKEND=redis://redis:6379/0
WS_MESSAGE_QUEUE=redis://redis:6379/0
RABBITMQ_DEFAULT_USER=admin
RABBITMQ_DEFAULT_PASS=admin
CELERY_FLOWER_USER=admin
CELERY_FLOWER_PASSWORD=admin
```

## Troubleshooting

### Common Issues

1. **Celery tasks not executing:**

   - Check worker is running: `docker-compose logs celery_worker`
   - Verify Redis/RabbitMQ connection
   - Check task routing configuration

2. **Database connection errors:**

   - Ensure PostgreSQL is running: `docker-compose ps db`
   - Check DATABASE_URL in environment variables
   - Run migrations: `alembic upgrade head`

3. **WebSocket connection failed:**

   - Check browser console for errors
   - Verify Redis is running for message queue
   - Check Nginx configuration (production)

4. **Import errors:**
   - Rebuild Docker images: `docker-compose build`
   - Check Python path configuration
   - Verify requirements.txt is up to date

### Debugging Tips

1. **View logs:**

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery_worker
```

2. **Access container shell:**

```bash
docker-compose exec web bash
```

3. **Celery debugging:**

```python
# In tasks.py
from celery.contrib import rdb
rdb.set_trace()  # Breakpoint for Celery tasks
```

4. **Database queries:**

```bash
docker-compose exec db psql -U fastapi_celery -d fastapi_celery
```

## Best Practices

1. **Task Design:**

   - Keep tasks idempotent
   - Use task retry mechanisms
   - Log task progress for debugging

2. **API Design:**

   - Use Pydantic for request/response validation
   - Implement proper error handling
   - Document endpoints with OpenAPI schemas

3. **Database:**

   - Always use migrations for schema changes
   - Use database transactions appropriately
   - Implement proper connection pooling

4. **Security:**

   - Never commit `.env` files
   - Use environment-specific configurations
   - Implement authentication/authorization as needed

5. **Performance:**
   - Use task queues for long-running operations
   - Implement caching where appropriate
   - Monitor with Flower dashboard

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## Support

For questions or issues:

1. Check this documentation
2. Review existing code patterns in the project
3. Check logs for error messages
4. Consult team lead or senior developers

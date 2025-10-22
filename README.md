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

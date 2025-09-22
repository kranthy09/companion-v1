from project import create_app

app = create_app()
celery = app.celery_app

# Project metadata
app.title = "Companion App API"
app.description = "A FastAPI application with Celery for background tasks"
app.version = "1.0.0"

# Additional metadata
app.contact = {
    "name": "Companion",
    "url": "https://example.com/contact/",
    "email": "contact@example.com",
}

app.license_info = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT",
}

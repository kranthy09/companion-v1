"""
companion/project/asgi.py

Asgi app with celery
"""

from project import create_app

app = create_app()
celery = app.celery_app

from contextlib import asynccontextmanager
from broadcaster import Broadcast
from fastapi import FastAPI

from project.config import settings

broadcast = Broadcast(settings.WS_MESSAGE_QUEUE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broadcast.connect()
    yield
    await broadcast.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    from project.logging import configure_logging

    configure_logging()

    # Add security middleware
    from project.middleware.rate_limiter import rate_limit_middleware
    from project.middleware.throttler import throttle_middleware

    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(throttle_middleware)

    # do this before loading routes
    from project.celery_utils import create_celery

    app.celery_app = create_celery()

    # Include authentication routes
    from project.auth import auth_router

    app.include_router(auth_router)

    # Include existing routes
    from project.users import users_router

    app.include_router(users_router)

    from project.ws import ws_router

    app.include_router(ws_router)

    from project.ws.views import register_socketio_app

    register_socketio_app(app)

    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    return app

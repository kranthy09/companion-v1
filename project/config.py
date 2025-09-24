"""
companion/project/config.py

Project configuration file, with environment configs
"""

import os
import pathlib
from functools import lru_cache
from kombu import Queue


def route_task(name, args, kwargs, options, task=None, **kw):
    if ":" in name:
        queue, _ = name.split(":")
        return {"queue": queue}
    return {"queue": "default"}


class BaseConfig:
    BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent

    DATABASE_URL: str = os.environ.get("DATABASE_URL")
    FASTAPI_CONFIG: str = os.environ.get("FASTAPI_CONFIG")
    DATABASE_CONNECT_DICT: dict = {}

    # JWT Configuration - MOVED TO ENVIRONMENT
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "dev-only-key-change-in-production"  # Shorter default
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )

    # Security
    CORS_ORIGINS: list = os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"
    ).split(",")

    # Database Pool Settings
    DATABASE_POOL_SIZE: int = int(os.environ.get("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(
        os.environ.get("DATABASE_MAX_OVERFLOW", "20")
    )
    DATABASE_POOL_PRE_PING: bool = True  # Check connections before using

    # Celery Configuration
    CELERY_BROKER_URL: str = os.environ.get(
        "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"
    )
    CELERY_RESULT_BACKEND: str = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0"
    )
    CELERY_TASK_ALWAYS_EAGER: bool = False
    WS_MESSAGE_QUEUE: str = os.environ.get(
        "WS_MESSAGE_QUEUE", "redis://127.0.0.1:6379/0"
    )
    CELERY_BEAT_SCHEDULE: dict = {
        # "task-schedule-work": {
        #     "task": "task_schedule_work",
        #     "schedule": 5.0,  # five seconds
        # },
    }
    CELERY_TASK_DEFAULT_QUEUE: str = "default"

    # Force all queues to be explicitly listed in `CELERY_TASK_QUEUES`
    # # to help prevent typos
    CELERY_TASK_CREATE_MISSING_QUEUES: bool = False

    CELERY_TASK_QUEUES: list = (
        # need to define default queue here or exception would be raised
        Queue("default"),
        Queue("high_priority"),
        Queue("low_priority"),
    )
    CELERY_TASK_ROUTES = {
        "project.users.tasks.*": {
            "queue": "high_priority",
        },
    }
    CELERY_TASK_ROUTES = (route_task,)


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    # Enforce SECRET_KEY in production
    SECRET_KEY: str = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError(
            "SECRET_KEY environment variable is required in production"
        )


class TestingConfig(BaseConfig):
    DATABASE_URL: str = "sqlite:///./test.db"
    DATABASE_CONNECT_DICT: dict = {"check_same_thread": False}
    SECRET_KEY: str = "test-secret-key"
    CELERY_TASK_ALWAYS_EAGER: bool = True


@lru_cache()
def get_settings():
    config_cls_dict = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }

    config_name = os.environ.get("FASTAPI_CONFIG", "development")
    config_cls = config_cls_dict[config_name]
    return config_cls()


settings = get_settings()

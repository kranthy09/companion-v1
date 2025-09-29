"""
project/celery_logging.py - Request ID propagation to Celery
"""

import logging
from celery import Task
from celery.signals import before_task_publish, task_prerun

logger = logging.getLogger(__name__)


class RequestContextTask(Task):
    """Base task that carries request context"""

    def __call__(self, *args, **kwargs):
        # Extract request_id from task headers
        request_id = self.request.get("request_id")

        if request_id:
            # Add to all log records in this task
            extra = {"request_id": request_id}
            logger.info(f"Task {self.name} started", extra={"extra": extra})

        return super().__call__(*args, **kwargs)


@before_task_publish.connect
def add_request_id_to_task(sender=None, headers=None, body=None, **kwargs):
    """Add request_id to task headers when publishing"""
    from contextvars import ContextVar

    # Get current request_id from context if available
    request_id_var: ContextVar = ContextVar("request_id", default=None)
    request_id = request_id_var.get()

    if request_id and headers:
        headers["request_id"] = request_id


@task_prerun.connect
def log_task_prerun(task_id, task, args, kwargs, **extra):
    """Log when task starts"""
    request_id = task.request.get("request_id")
    log_extra = {
        "task_id": task_id,
        "task_name": task.name,
    }
    if request_id:
        log_extra["request_id"] = request_id

    logger.info("Celery task starting", extra={"extra": log_extra})

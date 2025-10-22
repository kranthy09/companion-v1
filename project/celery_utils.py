"""Production-optimized Celery configuration"""

from celery import Celery, Task
from celery.signals import task_prerun, task_postrun, task_failure
from project.config import settings
import logging

logger = logging.getLogger(__name__)


class OptimizedTask(Task):
    """Base task with connection pooling and retries"""

    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 5}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    # Cleanup after task
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Clean up resources after task completes"""
        # Close DB connections
        from project.database import SessionLocal
        SessionLocal.close_all()


def create_celery() -> Celery:
    """Create optimized Celery app"""

    celery_app = Celery(
        "project",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        task_cls=OptimizedTask
    )

    celery_app.conf.update(
        # Task execution
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,

        # Performance
        task_acks_late=True,  # Acknowledge after completion
        worker_prefetch_multiplier=4,  # Prefetch for efficiency
        worker_max_tasks_per_child=1000,  # Restart workers periodically

        # Results
        result_expires=3600,  # 1 hour
        result_backend_transport_options={
            'master_name': 'mymaster',
            'socket_keepalive': True,
            'retry_on_timeout': True,
            'max_connections': 50
        },

        # Broker connection
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
        broker_pool_limit=50,

        # Task routing
        task_routes=settings.CELERY_TASK_ROUTES,
        task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
        task_queues=settings.CELERY_TASK_QUEUES,
        task_create_missing_queues=settings.CELERY_TASK_CREATE_MISSING_QUEUES,

        # Beat schedule
        beat_schedule=settings.CELERY_BEAT_SCHEDULE,

        # Logging
        worker_redirect_stdouts=False,

        # Task time limits
        task_soft_time_limit=300,  # 5 minutes soft
        task_time_limit=600,  # 10 minutes hard

        # Optimization
        task_compression='gzip',
        result_compression='gzip',

        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    # Task autodiscovery
    celery_app.autodiscover_tasks([
        'project.users',
        'project.notes',
        'project.ollama',
        'project.blog',
        'project.tasks'
    ])

    return celery_app


def get_task_info(task_id: str) -> dict:
    """Get Celery task status and result"""
    from celery.result import AsyncResult

    celery_app = create_celery()
    result = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "state": result.state,
        "status": result.status,
        "result": result.result if result.successful() else None,
        "error": str(result.info) if result.failed() else None,
    }


# Monitoring signals
@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Log task start"""
    logger.info(f"Task {task.name} [{task_id}] started")


@task_postrun.connect
def task_postrun_handler(task_id, task, retval, *args, **kwargs):
    """Log task completion"""
    logger.info(f"Task {task.name} [{task_id}] completed")


@task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    """Log task failure"""
    logger.error(f"Task [{task_id}] failed: {exception}")

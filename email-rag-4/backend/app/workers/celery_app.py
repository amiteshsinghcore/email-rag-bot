"""
Celery Application Configuration

Configures the Celery application for background task processing.
"""

from celery import Celery

from app.config import settings

# Create Celery application
celery_app = Celery(
    "email_rag",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.workers.email_tasks",
        "app.workers.indexing_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 min soft limit

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # Number of concurrent workers

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata

    # Task routing
    task_routes={
        "app.workers.email_tasks.*": {"queue": "email_processing"},
        "app.workers.indexing_tasks.*": {"queue": "indexing"},
    },

    # Task rate limits
    task_annotations={
        "app.workers.email_tasks.process_pst_file": {
            "rate_limit": "2/m",  # Max 2 PST files per minute
        },
    },

    # Beat schedule for periodic tasks (if needed)
    beat_schedule={
        # Example: cleanup old tasks every hour
        # "cleanup-old-tasks": {
        #     "task": "app.workers.maintenance_tasks.cleanup_old_tasks",
        #     "schedule": 3600.0,
        # },
    },
)


def get_celery_app() -> Celery:
    """Get the Celery application instance."""
    return celery_app

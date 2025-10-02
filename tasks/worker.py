from celery import Celery
from app.core.config import settings
import structlog

# Configure structured logging for worker
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "hospup_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        'tasks.video_processing_tasks'
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    task_routes={
        'tasks.video_processing_tasks.*': {'queue': 'video_processing'},
    },
    task_default_queue='default',
)

@celery_app.task(bind=True)
def debug_task(self):
    logger.info("Debug task executed", task_id=self.request.id)
    return f'Request: {self.request!r}'
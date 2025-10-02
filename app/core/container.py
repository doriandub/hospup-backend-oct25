"""
Dependency Injection Container

Central configuration for all application dependencies.
Implements the Dependency Inversion Principle by providing
concrete implementations for abstract interfaces.
"""

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide
import structlog

from ..infrastructure.cache.redis_cache_service import RedisCacheService
from ..application.use_cases.generate_video_use_case import GenerateVideoUseCase
from ..application.interfaces import (
    IAIMatchingService,
    IVideoProcessingService,
    IQuotaService,
    IEventPublisher,
    IStorageService,
    INotificationService,
    IAnalyticsService
)
from ..application.interfaces.cache_service import ICacheService
from ..domain.repositories.property_repository import IPropertyRepository
from ..domain.repositories.video_repository import IVideoRepository

logger = structlog.get_logger(__name__)


class ApplicationContainer(containers.DeclarativeContainer):
    """
    Application dependency injection container

    Configures all dependencies and their relationships.
    This is the composition root of the application.
    """

    # Configuration
    config = providers.Configuration()

    # Database
    database = providers.Resource(
        providers.Factory(
            "app.infrastructure.database.database_factory.create_database",
            database_url=config.database_url,
            echo=config.database_echo.as_(bool),
            pool_size=config.database_pool_size.as_(int),
            max_overflow=config.database_max_overflow.as_(int)
        )
    )

    # Cache Service
    cache_service = providers.Singleton(
        RedisCacheService,
        redis_url=config.redis_url,
        max_connections=config.redis_max_connections.as_(int),
        socket_timeout=config.redis_socket_timeout.as_(float),
        socket_connect_timeout=config.redis_connect_timeout.as_(float)
    )

    # Repositories
    property_repository = providers.Factory(
        "app.infrastructure.repositories.property_repository.PostgresPropertyRepository",
        database=database
    )

    video_repository = providers.Factory(
        "app.infrastructure.repositories.video_repository.PostgresVideoRepository",
        database=database
    )

    # External Services
    ai_matching_service = providers.Factory(
        "app.infrastructure.external.openai_matching_service.OpenAIMatchingService",
        api_key=config.openai_api_key,
        cache_service=cache_service
    )

    video_processing_service = providers.Factory(
        "app.infrastructure.external.aws_video_processing_service.AWSVideoProcessingService",
        lambda_function_name=config.aws_lambda_function_name,
        aws_region=config.aws_region,
        cache_service=cache_service
    )

    storage_service = providers.Factory(
        "app.infrastructure.external.s3_storage_service.S3StorageService",
        bucket_name=config.s3_bucket_name,
        aws_region=config.aws_region,
        access_key_id=config.s3_access_key_id,
        secret_access_key=config.s3_secret_access_key
    )

    quota_service = providers.Factory(
        "app.infrastructure.services.quota_service.DatabaseQuotaService",
        database=database,
        cache_service=cache_service
    )

    event_publisher = providers.Factory(
        "app.infrastructure.messaging.event_publisher.CeleryEventPublisher",
        broker_url=config.celery_broker_url
    )

    notification_service = providers.Factory(
        "app.infrastructure.services.notification_service.EmailNotificationService",
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port.as_(int),
        smtp_username=config.smtp_username,
        smtp_password=config.smtp_password
    )

    analytics_service = providers.Factory(
        "app.infrastructure.services.analytics_service.DatabaseAnalyticsService",
        database=database,
        cache_service=cache_service
    )

    # Use Cases
    generate_video_use_case = providers.Factory(
        GenerateVideoUseCase,
        video_repository=video_repository,
        property_repository=property_repository,
        ai_service=ai_matching_service,
        processing_service=video_processing_service,
        quota_service=quota_service,
        cache_service=cache_service,
        event_publisher=event_publisher
    )

    create_property_use_case = providers.Factory(
        "app.application.use_cases.create_property_use_case.CreatePropertyUseCase",
        property_repository=property_repository,
        quota_service=quota_service,
        event_publisher=event_publisher
    )

    # Health Check Service
    health_service = providers.Factory(
        "app.infrastructure.monitoring.health_service.HealthService",
        database=database,
        cache_service=cache_service,
        external_services=[
            ai_matching_service,
            video_processing_service,
            storage_service
        ]
    )


# Global container instance
container = ApplicationContainer()


def init_container(config_dict: dict) -> None:
    """
    Initialize container with configuration

    Args:
        config_dict: Configuration dictionary from settings
    """
    try:
        container.config.from_dict(config_dict)
        logger.info("Dependency injection container initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize container", error=str(e))
        raise


async def setup_container() -> None:
    """Setup container resources (async initialization)"""
    try:
        await container.init_resources()
        logger.info("Container resources initialized successfully")
    except Exception as e:
        logger.error("Failed to setup container resources", error=str(e))
        raise


async def cleanup_container() -> None:
    """Cleanup container resources"""
    try:
        await container.shutdown_resources()
        logger.info("Container resources cleaned up successfully")
    except Exception as e:
        logger.error("Failed to cleanup container resources", error=str(e))


# Dependency providers for FastAPI dependency injection
def get_cache_service() -> ICacheService:
    """Get cache service instance"""
    return container.cache_service()


def get_video_repository() -> IVideoRepository:
    """Get video repository instance"""
    return container.video_repository()


def get_property_repository() -> IPropertyRepository:
    """Get property repository instance"""
    return container.property_repository()


def get_generate_video_use_case() -> GenerateVideoUseCase:
    """Get generate video use case instance"""
    return container.generate_video_use_case()


def get_ai_matching_service() -> IAIMatchingService:
    """Get AI matching service instance"""
    return container.ai_matching_service()


def get_video_processing_service() -> IVideoProcessingService:
    """Get video processing service instance"""
    return container.video_processing_service()


def get_quota_service() -> IQuotaService:
    """Get quota service instance"""
    return container.quota_service()


def get_storage_service() -> IStorageService:
    """Get storage service instance"""
    return container.storage_service()


def get_notification_service() -> INotificationService:
    """Get notification service instance"""
    return container.notification_service()


def get_analytics_service() -> IAnalyticsService:
    """Get analytics service instance"""
    return container.analytics_service()


def get_health_service():
    """Get health service instance"""
    return container.health_service()


# Export all providers
__all__ = [
    'container',
    'init_container',
    'setup_container',
    'cleanup_container',
    'get_cache_service',
    'get_video_repository',
    'get_property_repository',
    'get_generate_video_use_case',
    'get_ai_matching_service',
    'get_video_processing_service',
    'get_quota_service',
    'get_storage_service',
    'get_notification_service',
    'get_analytics_service',
    'get_health_service'
]
"""
Shared Application Exceptions

Centralized exception hierarchy for the entire application.
Provides consistent error handling across all layers.
"""

from typing import Optional, Dict, Any


class ApplicationError(Exception):
    """Base application exception"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


class ConfigurationError(ApplicationError):
    """Configuration or setup error"""
    pass


class ValidationError(ApplicationError):
    """Input validation error"""
    pass


class AuthenticationError(ApplicationError):
    """Authentication failed"""
    pass


class AuthorizationError(ApplicationError):
    """Authorization failed"""
    pass


class NotFoundError(ApplicationError):
    """Resource not found"""
    pass


class ConflictError(ApplicationError):
    """Resource conflict (duplicate, etc.)"""
    pass


class ExternalServiceError(ApplicationError):
    """External service error (API, database, etc.)"""
    pass


class StorageError(ExternalServiceError):
    """File storage service error"""
    pass


class DatabaseError(ExternalServiceError):
    """Database operation error"""
    pass


class CacheError(ExternalServiceError):
    """Cache service error"""
    pass


class AIServiceError(ExternalServiceError):
    """AI service error (OpenAI, etc.)"""
    pass


class RateLimitError(ApplicationError):
    """Rate limit exceeded"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after


class QuotaExceededError(ApplicationError):
    """User quota exceeded"""

    def __init__(self, resource: str, current: int, limit: int):
        message = f"{resource.capitalize()} quota exceeded: {current}/{limit}"
        super().__init__(
            message,
            "QUOTA_EXCEEDED",
            {"resource": resource, "current": current, "limit": limit}
        )


class BusinessRuleViolationError(ApplicationError):
    """Business rule violation"""
    pass


class ProcessingError(ApplicationError):
    """Processing operation error"""
    pass


class VideoGenerationError(ProcessingError):
    """Video generation specific error"""
    pass


class TemplateNotFoundError(NotFoundError):
    """Template not found"""
    pass


class PropertyNotFoundError(NotFoundError):
    """Property not found"""
    pass


class VideoNotFoundError(NotFoundError):
    """Video not found"""
    pass


class UserNotFoundError(NotFoundError):
    """User not found"""
    pass
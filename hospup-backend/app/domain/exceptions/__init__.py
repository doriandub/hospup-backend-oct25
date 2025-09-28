"""
Domain Exceptions

Business-specific exceptions that represent domain rule violations.
These exceptions are part of the domain language and express business concepts.
"""

from typing import Optional, Dict, Any


class DomainException(Exception):
    """Base domain exception"""

    def __init__(self, message: str, error_code: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.metadata = metadata or {}


class ValidationError(DomainException):
    """Base validation error"""
    pass


class BusinessRuleViolationError(DomainException):
    """Business rule violation error"""
    pass


# Property-related exceptions
class PropertyValidationError(ValidationError):
    """Property validation failed"""
    pass


class PropertyNotFoundError(DomainException):
    """Property not found"""
    pass


class PropertyAlreadyExistsError(DomainException):
    """Property already exists for user"""
    pass


class PropertyQuotaExceededError(BusinessRuleViolationError):
    """Property creation quota exceeded"""

    def __init__(self, current_count: int, max_allowed: int):
        super().__init__(
            f"Property quota exceeded: {current_count}/{max_allowed}",
            error_code="PROPERTY_QUOTA_EXCEEDED",
            metadata={
                "current_count": current_count,
                "max_allowed": max_allowed
            }
        )


# Video-related exceptions
class VideoValidationError(ValidationError):
    """Video validation failed"""
    pass


class VideoNotFoundError(DomainException):
    """Video not found"""
    pass


class InvalidVideoStateError(DomainException):
    """Video is in invalid state for requested operation"""
    pass


class VideoQuotaExceededError(BusinessRuleViolationError):
    """Video generation quota exceeded"""

    def __init__(self, current_count: int, max_allowed: int, period: str = "monthly"):
        super().__init__(
            f"Video quota exceeded: {current_count}/{max_allowed} for {period}",
            error_code="VIDEO_QUOTA_EXCEEDED",
            metadata={
                "current_count": current_count,
                "max_allowed": max_allowed,
                "period": period
            }
        )


class VideoProcessingError(DomainException):
    """Video processing failed"""
    pass


class VideoGenerationTimeoutError(DomainException):
    """Video generation timed out"""
    pass


# User-related exceptions
class UserValidationError(ValidationError):
    """User validation failed"""
    pass


class UserNotFoundError(DomainException):
    """User not found"""
    pass


class UserAlreadyExistsError(DomainException):
    """User already exists"""
    pass


class InsufficientPermissionsError(DomainException):
    """User has insufficient permissions"""
    pass


# Authentication exceptions
class AuthenticationError(DomainException):
    """Authentication failed"""
    pass


class AuthorizationError(DomainException):
    """Authorization failed"""
    pass


class TokenExpiredError(AuthenticationError):
    """Token has expired"""
    pass


class InvalidTokenError(AuthenticationError):
    """Token is invalid"""
    pass


# External service exceptions
class ExternalServiceError(DomainException):
    """External service error"""
    pass


class AIServiceError(ExternalServiceError):
    """AI service error"""
    pass


class StorageServiceError(ExternalServiceError):
    """Storage service error"""
    pass


class VideoProcessingServiceError(ExternalServiceError):
    """Video processing service error"""
    pass


# Rate limiting exceptions
class RateLimitExceededError(DomainException):
    """Rate limit exceeded"""

    def __init__(self, limit: int, window: int, retry_after: int):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window} seconds",
            error_code="RATE_LIMIT_EXCEEDED",
            metadata={
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            }
        )


# Template exceptions
class TemplateNotFoundError(DomainException):
    """Template not found"""
    pass


class InvalidTemplateError(DomainException):
    """Template is invalid"""
    pass


# Asset exceptions
class AssetNotFoundError(DomainException):
    """Asset not found"""
    pass


class AssetValidationError(ValidationError):
    """Asset validation failed"""
    pass


class AssetProcessingError(DomainException):
    """Asset processing failed"""
    pass


class AssetQuotaExceededError(BusinessRuleViolationError):
    """Asset storage quota exceeded"""

    def __init__(self, current_size: int, max_allowed: int):
        super().__init__(
            f"Asset storage quota exceeded: {current_size}MB/{max_allowed}MB",
            error_code="ASSET_QUOTA_EXCEEDED",
            metadata={
                "current_size_mb": current_size,
                "max_allowed_mb": max_allowed
            }
        )


# Export all exceptions
__all__ = [
    # Base exceptions
    'DomainException',
    'ValidationError',
    'BusinessRuleViolationError',

    # Property exceptions
    'PropertyValidationError',
    'PropertyNotFoundError',
    'PropertyAlreadyExistsError',
    'PropertyQuotaExceededError',

    # Video exceptions
    'VideoValidationError',
    'VideoNotFoundError',
    'InvalidVideoStateError',
    'VideoQuotaExceededError',
    'VideoProcessingError',
    'VideoGenerationTimeoutError',

    # User exceptions
    'UserValidationError',
    'UserNotFoundError',
    'UserAlreadyExistsError',
    'InsufficientPermissionsError',

    # Auth exceptions
    'AuthenticationError',
    'AuthorizationError',
    'TokenExpiredError',
    'InvalidTokenError',

    # External service exceptions
    'ExternalServiceError',
    'AIServiceError',
    'StorageServiceError',
    'VideoProcessingServiceError',

    # Rate limiting
    'RateLimitExceededError',

    # Template exceptions
    'TemplateNotFoundError',
    'InvalidTemplateError',

    # Asset exceptions
    'AssetNotFoundError',
    'AssetValidationError',
    'AssetProcessingError',
    'AssetQuotaExceededError',
]
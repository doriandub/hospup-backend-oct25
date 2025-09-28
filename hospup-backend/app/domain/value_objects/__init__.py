"""
Domain Value Objects

Immutable objects that describe aspects of the domain with no conceptual identity.
Value objects are compared by their attributes, not identity.
"""

from dataclasses import dataclass
from typing import Union, Optional
import re
from datetime import datetime


@dataclass(frozen=True)
class UserId:
    """User identifier value object"""
    value: int

    def __post_init__(self):
        if self.value <= 0:
            raise ValueError("User ID must be positive")


@dataclass(frozen=True)
class PropertyId:
    """Property identifier value object"""
    value: Union[int, str]

    def __post_init__(self):
        if isinstance(self.value, int) and self.value <= 0:
            raise ValueError("Property ID must be positive")
        if isinstance(self.value, str) and not self.value.strip():
            raise ValueError("Property ID cannot be empty")


@dataclass(frozen=True)
class VideoId:
    """Video identifier value object"""
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("Video ID cannot be empty")


@dataclass(frozen=True)
class Email:
    """Email value object with validation"""
    value: str

    def __post_init__(self):
        if not self._is_valid_email(self.value):
            raise ValueError(f"Invalid email address: {self.value}")

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @property
    def domain(self) -> str:
        """Get email domain"""
        return self.value.split('@')[1]

    @property
    def local_part(self) -> str:
        """Get local part of email"""
        return self.value.split('@')[0]


@dataclass(frozen=True)
class PropertyName:
    """Property name value object with business rules"""
    value: str

    def __post_init__(self):
        if not self.value or len(self.value.strip()) < 2:
            raise ValueError("Property name must be at least 2 characters")
        if len(self.value) > 100:
            raise ValueError("Property name cannot exceed 100 characters")

        # Clean the value
        object.__setattr__(self, 'value', self.value.strip())

    def is_valid(self) -> bool:
        """Check if property name is valid"""
        return len(self.value.strip()) >= 2 and len(self.value) <= 100

    @property
    def slug(self) -> str:
        """Generate URL-friendly slug"""
        return re.sub(r'[^a-z0-9]+', '-', self.value.lower()).strip('-')


@dataclass(frozen=True)
class ContactInfo:
    """Contact information value object"""
    email: Optional[Email] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None

    def is_complete(self) -> bool:
        """Business rule: Contact info is complete if email is provided"""
        return self.email is not None

    def has_phone(self) -> bool:
        """Check if phone number is provided"""
        return self.phone is not None and len(self.phone.strip()) > 0

    def has_address(self) -> bool:
        """Check if address is provided"""
        return self.address is not None and len(self.address.strip()) > 0


@dataclass(frozen=True)
class VideoUrl:
    """Video URL value object with validation"""
    value: str

    def __post_init__(self):
        if not self._is_valid_url(self.value):
            raise ValueError(f"Invalid video URL: {self.value}")

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))

    @property
    def is_s3_url(self) -> bool:
        """Check if URL is an S3 URL"""
        return 's3' in self.value and 'amazonaws.com' in self.value

    @property
    def filename(self) -> str:
        """Extract filename from URL"""
        return self.value.split('/')[-1]


@dataclass(frozen=True)
class Duration:
    """Duration value object with validation"""
    total_seconds: float

    def __post_init__(self):
        if self.total_seconds < 0:
            raise ValueError("Duration cannot be negative")
        if self.total_seconds > 3600:  # 1 hour max
            raise ValueError("Duration cannot exceed 1 hour")

    @property
    def minutes(self) -> int:
        """Get duration in minutes"""
        return int(self.total_seconds // 60)

    @property
    def seconds(self) -> int:
        """Get remaining seconds after minutes"""
        return int(self.total_seconds % 60)

    def __str__(self) -> str:
        """Human readable duration"""
        if self.total_seconds < 60:
            return f"{self.total_seconds:.1f}s"
        return f"{self.minutes}m {self.seconds}s"

    @classmethod
    def from_minutes(cls, minutes: float) -> "Duration":
        """Create duration from minutes"""
        return cls(minutes * 60)

    @classmethod
    def from_seconds(cls, seconds: float) -> "Duration":
        """Create duration from seconds"""
        return cls(seconds)


@dataclass(frozen=True)
class Money:
    """Money value object for pricing"""
    amount: float
    currency: str = "USD"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if len(self.currency) != 3:
            raise ValueError("Currency must be 3-letter ISO code")

        # Normalize currency
        object.__setattr__(self, 'currency', self.currency.upper())

    def __str__(self) -> str:
        """String representation"""
        return f"{self.amount:.2f} {self.currency}"

    def __add__(self, other: "Money") -> "Money":
        """Add money amounts"""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, factor: float) -> "Money":
        """Multiply money by factor"""
        return Money(self.amount * factor, self.currency)


# Export all value objects
__all__ = [
    'UserId',
    'PropertyId',
    'VideoId',
    'Email',
    'PropertyName',
    'ContactInfo',
    'VideoUrl',
    'Duration',
    'Money'
]
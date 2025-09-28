"""
Property Domain Entity - Core Business Logic
Pure domain entity with business rules and invariants
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

from ..value_objects import PropertyId, UserId, PropertyName, ContactInfo
from ..exceptions import PropertyValidationError, QuotaExceededError
from ..events import PropertyCreated, PropertyUpdated


class PropertyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PropertyType(Enum):
    HOTEL = "hotel"
    RESTAURANT = "restaurant"
    RESORT = "resort"
    B_AND_B = "bed_and_breakfast"


@dataclass
class Property:
    """
    Property Domain Entity

    Core business entity representing a hospitality property.
    Contains all business rules and invariants for properties.
    """

    id: Optional[PropertyId]
    user_id: UserId
    name: PropertyName
    contact_info: ContactInfo
    property_type: PropertyType
    status: PropertyStatus = PropertyStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Domain events
    _events: List = field(default_factory=list, init=False)

    def __post_init__(self):
        """Validate entity invariants on creation"""
        self._validate_business_rules()

        if not self.id:  # New property
            self._add_event(PropertyCreated(
                property_id=self.id,
                user_id=self.user_id,
                name=self.name.value,
                property_type=self.property_type
            ))

    def _validate_business_rules(self) -> None:
        """Enforce business rules and invariants"""
        if not self.name.is_valid():
            raise PropertyValidationError("Property name must be at least 2 characters")

        if not self.contact_info.is_complete():
            raise PropertyValidationError("Contact information must be complete")

        if self.property_type == PropertyType.HOTEL and len(self.name.value) < 5:
            raise PropertyValidationError("Hotel names must be at least 5 characters")

    def update_contact_info(self, new_contact: ContactInfo) -> None:
        """Update contact information with validation"""
        if not new_contact.is_complete():
            raise PropertyValidationError("Contact information must be complete")

        old_contact = self.contact_info
        self.contact_info = new_contact
        self.updated_at = datetime.utcnow()

        self._add_event(PropertyUpdated(
            property_id=self.id,
            field="contact_info",
            old_value=old_contact,
            new_value=new_contact
        ))

    def can_generate_videos(self) -> bool:
        """Business rule: Check if property can generate videos"""
        return (
            self.status == PropertyStatus.ACTIVE and
            self.contact_info.is_complete() and
            self.name.is_valid()
        )

    def calculate_monthly_quota(self, user_plan: str) -> int:
        """Business rule: Calculate video generation quota based on plan"""
        base_quotas = {
            "FREE": 5,
            "STARTER": 20,
            "PRO": 50,
            "BUSINESS": 100,
            "ENTERPRISE": 500
        }

        base_quota = base_quotas.get(user_plan.upper(), 0)

        # Business rule: Hotels get 2x quota
        if self.property_type == PropertyType.HOTEL:
            return base_quota * 2

        # Business rule: Resorts get 1.5x quota
        if self.property_type == PropertyType.RESORT:
            return int(base_quota * 1.5)

        return base_quota

    def suspend(self, reason: str) -> None:
        """Suspend property with business validation"""
        if self.status == PropertyStatus.SUSPENDED:
            raise PropertyValidationError("Property is already suspended")

        old_status = self.status
        self.status = PropertyStatus.SUSPENDED
        self.updated_at = datetime.utcnow()

        self._add_event(PropertyUpdated(
            property_id=self.id,
            field="status",
            old_value=old_status,
            new_value=self.status,
            metadata={"reason": reason}
        ))

    def activate(self) -> None:
        """Activate property with validation"""
        if not self.can_generate_videos():
            raise PropertyValidationError("Property does not meet activation requirements")

        old_status = self.status
        self.status = PropertyStatus.ACTIVE
        self.updated_at = datetime.utcnow()

        self._add_event(PropertyUpdated(
            property_id=self.id,
            field="status",
            old_value=old_status,
            new_value=self.status
        ))

    def _add_event(self, event) -> None:
        """Add domain event"""
        self._events.append(event)

    def get_events(self) -> List:
        """Get and clear domain events"""
        events = self._events.copy()
        self._events.clear()
        return events

    @classmethod
    def create(
        cls,
        user_id: UserId,
        name: str,
        contact_info: ContactInfo,
        property_type: PropertyType
    ) -> "Property":
        """Factory method to create new property"""
        return cls(
            id=None,  # Will be generated by repository
            user_id=user_id,
            name=PropertyName(name),
            contact_info=contact_info,
            property_type=property_type
        )
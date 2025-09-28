"""
Property Repository Interface

Defines the contract for property data access.
This is part of the domain layer and defines what operations are needed,
not how they are implemented.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..entities.property import Property
from ..value_objects import UserId, PropertyId


class IPropertyRepository(ABC):
    """Property repository interface"""

    @abstractmethod
    async def save(self, property: Property) -> Property:
        """
        Save a property (create or update).
        Returns the saved property with generated ID if new.
        """
        pass

    @abstractmethod
    async def find_by_id(self, property_id: PropertyId) -> Optional[Property]:
        """Find property by ID"""
        pass

    @abstractmethod
    async def find_by_user_id(self, user_id: UserId) -> List[Property]:
        """Find all properties for a user"""
        pass

    @abstractmethod
    async def find_by_user_id_paginated(
        self,
        user_id: UserId,
        page: int = 1,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Find properties for user with pagination.
        Returns: {
            "items": List[Property],
            "total": int,
            "page": int,
            "size": int,
            "pages": int
        }
        """
        pass

    @abstractmethod
    async def count_by_user_id(self, user_id: UserId) -> int:
        """Count properties for a user"""
        pass

    @abstractmethod
    async def exists(self, property_id: PropertyId) -> bool:
        """Check if property exists"""
        pass

    @abstractmethod
    async def exists_by_name_and_user(self, name: str, user_id: UserId) -> bool:
        """Check if property with given name exists for user"""
        pass

    @abstractmethod
    async def delete(self, property_id: PropertyId) -> bool:
        """
        Delete a property.
        Returns True if deleted, False if not found.
        """
        pass

    @abstractmethod
    async def find_active_properties(self, user_id: UserId) -> List[Property]:
        """Find all active properties for a user"""
        pass

    @abstractmethod
    async def find_properties_with_stats(self, user_id: UserId) -> List[Dict[str, Any]]:
        """
        Find properties with statistics (video count, asset count, etc.)
        Returns list of dicts with property data and stats.
        """
        pass

    @abstractmethod
    async def search_properties(
        self,
        user_id: UserId,
        query: str,
        limit: int = 10
    ) -> List[Property]:
        """Search properties by name or description"""
        pass
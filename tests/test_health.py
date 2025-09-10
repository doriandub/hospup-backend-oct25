import pytest
from httpx import AsyncClient
from unittest.mock import patch

from main import app

@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Hospup API" in data["message"]

@pytest.mark.asyncio
async def test_health_endpoint_healthy():
    """Test health endpoint when services are healthy"""
    with patch('app.core.database.get_db') as mock_db, \
         patch('redis.asyncio.from_url') as mock_redis:
        
        # Mock database connection
        mock_db.return_value.__aenter__ = lambda self: mock_db
        mock_db.return_value.__aexit__ = lambda self, *args: None
        mock_db.execute.return_value.fetchone.return_value = (1,)
        
        # Mock Redis connection
        mock_redis_instance = mock_redis.return_value
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.close.return_value = None
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
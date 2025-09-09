import pytest
from httpx import AsyncClient
from unittest.mock import patch

from main import app

@pytest.mark.asyncio
async def test_register_success():
    """Test successful user registration"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Registration successful"
            assert data["user"]["email"] == "test@example.com"
            assert data["user"]["plan_type"] == "FREE"
            
            # Check cookies are set
            assert "access_token" in response.cookies
            assert "refresh_token" in response.cookies

@pytest.mark.asyncio
async def test_register_duplicate_email():
    """Test registration with duplicate email"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # First registration
            await client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            # Second registration with same email
            response = await client.post("/api/v1/auth/register", json={
                "email": "test@example.com", 
                "password": "anotherpassword123"
            })
            
            assert response.status_code == 409
            assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_success():
    """Test successful login"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register user first
            await client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            # Login
            response = await client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Login successful"
            assert data["user"]["email"] == "test@example.com"
            
            # Check cookies are set
            assert "access_token" in response.cookies
            assert "refresh_token" in response.cookies

@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            })
            
            assert response.status_code == 401
            assert "Incorrect email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_user():
    """Test getting current user info"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register and login
            login_response = await client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            # Extract cookies from login response
            cookies = login_response.cookies
            
            # Get current user
            response = await client.get("/api/v1/auth/me", cookies=cookies)
            
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"
            assert data["plan_type"] == "FREE"

@pytest.mark.asyncio
async def test_logout():
    """Test logout functionality"""
    with patch('app.auth.routes.check_rate_limit', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register user
            login_response = await client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            cookies = login_response.cookies
            
            # Logout
            response = await client.post("/api/v1/auth/logout", cookies=cookies)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Logout successful"
            
            # Verify cookies are cleared (they should be expired)
            for cookie in response.cookies.values():
                if cookie.name in ["access_token", "refresh_token"]:
                    assert cookie.value == ""

@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting on auth endpoints"""
    with patch('app.auth.routes.check_rate_limit', return_value=False):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            assert response.status_code == 429
            assert "Too many" in response.json()["detail"]
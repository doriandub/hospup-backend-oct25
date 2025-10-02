# Hospup Backend API

Modern, scalable FastAPI backend for the Hospup platform with Clean Architecture principles.

## 🏗️ Architecture

- **Clean Architecture** with Domain-Driven Design
- **FastAPI** with async/await support
- **PostgreSQL** with Supabase
- **Redis** for caching and rate limiting
- **AWS S3** for file storage
- **AWS Lambda** for video processing
- **Celery** for background tasks

## 🚀 Quick Start

1. **Environment Setup**
   ```bash
   cp .env.example .env
   # Configure your environment variables
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Development Server**
   ```bash
   uvicorn app.main:app --reload
   ```

## 📚 Documentation

- **[Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)** - Complete setup and deployment guide
- **[Architecture](docs/architecture/)** - System design and architectural decisions
- **[Setup Guides](docs/setup/)** - Service configuration guides
- **[Deployment](docs/deployment/)** - Production deployment instructions

## 🔧 Key Features

- **Video Processing** - Automated video generation with AWS Lambda + FFmpeg
- **Asset Management** - S3-based file upload and processing
- **User Authentication** - JWT-based auth with refresh tokens
- **Property Management** - Multi-tenant property system
- **AI Integration** - OpenAI Vision API for content analysis
- **Rate Limiting** - Configurable rate limits per endpoint
- **Health Monitoring** - Comprehensive health checks and diagnostics

## 🏃‍♂️ Development

```bash
# Run with hot reload
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Run type checks
mypy app/

# Format code
black app/
```

## 🌐 API Endpoints

- **Health**: `GET /health` - System health check
- **Auth**: `POST /api/v1/auth/*` - Authentication endpoints
- **Assets**: `GET|POST|DELETE /api/v1/assets/*` - File management
- **Videos**: `POST /api/v1/videos/*` - Video generation and management
- **Properties**: `GET|POST /api/v1/properties/*` - Property management

## 🔒 Security

- JWT authentication with secure refresh tokens
- Rate limiting on all endpoints
- CORS protection for production domains
- Input validation with Pydantic schemas
- SQL injection protection with SQLAlchemy ORM

Built with ❤️ for scalable SaaS architecture.

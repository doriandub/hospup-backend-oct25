# 🏨 Hospup - AI-Powered Hotel Social Media Management

**Hospup** is a social media management platform designed specifically for hospitality properties. It allows hotels to upload their video assets, organize them in a content library, and generate professional marketing videos using AI-powered templates.

## 🎯 Features

### 📚 Content Library
- Upload and manage hotel video assets (rooms, pools, restaurants, views)
- Automatic video processing and thumbnail generation
- S3-based cloud storage with CDN delivery
- Video metadata and organization

### 🎬 Video Generation
- AI-powered smart matching of videos to template slots
- Drag-and-drop timeline editor
- Text overlay editor with customizable styling
- Real-time preview before generation
- AWS MediaConvert for professional video processing

### 🤖 AI Smart Matching
- OpenAI-powered semantic matching
- Understands hospitality themes (rooms, spa, dining, views)
- Fallback keyword-based matching
- Confidence scoring for each match

### 🎨 Templates
- Pre-built viral video templates
- Configurable slot durations and timings
- Text overlay support with TTML subtitle burn-in
- Multi-property support

## 🏗️ Architecture

### Frontend (Next.js 15)
- **Framework:** Next.js 15.1.0 with React 18
- **Styling:** Tailwind CSS
- **UI Components:** Radix UI, Headless UI
- **State Management:** React hooks
- **API Client:** Fetch with custom API wrapper

### Backend (FastAPI)
- **Framework:** FastAPI (Python 3.9+)
- **Database:** PostgreSQL with SQLAlchemy (async)
- **Authentication:** JWT-based auth
- **Storage:** AWS S3 with presigned URLs
- **Video Processing:** AWS Lambda + MediaConvert
- **Caching:** Redis

### Infrastructure
- **Hosting:** Railway (backend), Vercel (frontend)
- **Storage:** AWS S3 (eu-west-1)
- **Video Processing:** AWS Lambda + MediaConvert
- **Database:** PostgreSQL on Railway
- **CDN:** S3 public URLs

## 📁 Project Structure

```
hospup-project/
├── hospup-frontend/          # Next.js frontend
│   ├── src/
│   │   ├── app/             # Next.js app router pages
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── services/        # Business logic services
│   │   └── lib/             # Utilities
│   └── package.json
│
├── hospup-backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   │   └── video_generation/  # Video generation module
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── core/           # Core config & database
│   │   └── infrastructure/ # S3, external services
│   ├── requirements.txt
│   └── main.py
│
└── docs/                    # Documentation
    ├── AWS-SETUP-GUIDE.md
    ├── CODE_DUPLICATES_REFACTORING.md
    └── ...
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ (frontend)
- Python 3.9+ (backend)
- PostgreSQL database
- AWS account (S3, Lambda, MediaConvert)
- OpenAI API key (optional, for smart matching)

### Frontend Setup

```bash
cd hospup-frontend
npm install
cp .env.example .env.local
# Configure .env.local with your backend URL
npm run dev
```

Frontend will run on http://localhost:3000

### Backend Setup

```bash
cd hospup-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure .env with database and AWS credentials
uvicorn main:app --reload
```

Backend will run on http://localhost:8000

## 🔧 Configuration

### Required Environment Variables

**Backend:**
- `DATABASE_URL` - PostgreSQL connection string
- `S3_BUCKET` - AWS S3 bucket name
- `S3_REGION` - AWS region (e.g., eu-west-1)
- `S3_ACCESS_KEY_ID` - AWS access key
- `S3_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_LAMBDA_FUNCTION_NAME` - Lambda function for video processing
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `SECRET_KEY` - JWT secret key

**Frontend:**
- `NEXT_PUBLIC_API_URL` - Backend API URL

See detailed setup guides in `/docs/`:
- [AWS Setup Guide](./docs/AWS-SETUP-GUIDE.md)
- [S3 Configuration](./docs/S3_CONFIGURATION.md)
- [OpenAI Setup](./docs/OPENAI_SETUP.md)

## 📖 Documentation

- **[AWS Setup Guide](./docs/AWS-SETUP-GUIDE.md)** - Complete AWS infrastructure setup
- **[Code Refactoring Roadmap](./docs/CODE_DUPLICATES_REFACTORING.md)** - Cleanup and optimization plan
- **[Next Steps](./docs/NEXT-STEPS.md)** - Future features and improvements
- **[Design Summary](./docs/DESIGN-FINAL-SUMMARY.md)** - Architecture decisions

## 🛠️ Development

### Running Tests
```bash
# Backend tests
cd hospup-backend
pytest

# Frontend tests
cd hospup-frontend
npm test
```

### Code Quality
```bash
# Backend linting
cd hospup-backend
black app/
isort app/

# Frontend linting
cd hospup-frontend
npm run lint
```

## 🌐 Deployment

### Frontend (Vercel)
- Connected to main branch
- Auto-deploys on push
- Environment variables configured in Vercel dashboard

### Backend (Railway)
- Connected to main branch
- Auto-deploys on push
- Environment variables configured in Railway dashboard

## 📊 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token

### Assets
- `GET /api/v1/assets` - List assets
- `POST /api/v1/upload/presigned-url` - Get S3 upload URL
- `POST /api/v1/upload/complete` - Complete upload

### Video Generation
- `POST /api/v1/video-generation/smart-match` - AI smart matching
- `POST /api/v1/video-generation/generate-from-viral-template` - Generate video
- `GET /api/v1/video-generation/status/{job_id}` - Check generation status

See API documentation: http://localhost:8000/docs (when backend is running)

## 🤝 Contributing

This is a private project. For questions or access requests, please contact the project owner.

## 📝 License

Proprietary - All rights reserved

## 🆘 Support

For issues or questions:
1. Check the `/docs/` directory for detailed guides
2. Review error logs in Railway/Vercel dashboards
3. Check AWS CloudWatch for Lambda/MediaConvert logs
4. Contact the development team

---

**Built with ❤️ for the hospitality industry**

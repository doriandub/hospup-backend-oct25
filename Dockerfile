# Dockerfile for Railway deployment - Python FastAPI backend
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy backend files
COPY hospup-backend/requirements.txt .
COPY hospup-backend/ .

# Install system dependencies for compilation + video processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    curl \
    ffmpeg \
    libsm6 \
    libxext6 \
    libfontconfig1 \
    libxrender1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (Railway will set PORT env var)
EXPOSE 8000

# Start command
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

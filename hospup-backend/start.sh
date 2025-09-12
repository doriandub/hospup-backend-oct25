#!/bin/bash
# Railway startup script
# Gets the PORT from environment variable or defaults to 8000

PORT=${PORT:-8000}
echo "Starting FastAPI server on port $PORT"
exec uvicorn main:app --host 0.0.0.0 --port $PORT
# Railway deployment processes
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: celery -A tasks.worker worker --concurrency=2 --loglevel=info
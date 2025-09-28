# AWS Lambda - Video Generator

## Overview

This directory contains the AWS Lambda function for video generation processing.

## Structure

```
aws-lambda/
├── video-generator.py     # Main Lambda function
├── requirements.txt       # Python dependencies (minimal)
├── deploy.sh             # Deployment script
└── archives/             # Old ZIP files (archived)
```

## Clean Architecture

- **Single responsibility**: Video processing only
- **Minimal dependencies**: Only essential packages
- **Error handling**: Structured logging and callbacks
- **Monitoring**: Health checks and metrics

## Dependencies

```txt
requests>=2.31.0
Pillow>=10.0.0
```

## Deployment

```bash
./deploy.sh
```

This creates a lightweight deployment package (~5MB) instead of the previous 475MB.
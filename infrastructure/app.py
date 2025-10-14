#!/usr/bin/env python3
"""
🚀 AWS CDK Application - Hospup Video Processing Infrastructure
Infrastructure as Code pour ECS Fargate + FFmpeg avec warm pool
"""

import os
from aws_cdk import (
    App,
    Environment,
    Tags
)
from stacks.video_processing_stack import VideoProcessingStack

app = App()

# Configuration
env = Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT', '412655955859'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'eu-west-1')
)

# Paramètres configurables
warm_pool_size = int(app.node.try_get_context('warm_pool_size') or 10)
max_workers = int(app.node.try_get_context('max_workers') or 50)

# Créer le stack
stack = VideoProcessingStack(
    app,
    "HospupVideoProcessing",
    env=env,
    warm_pool_size=warm_pool_size,
    max_workers=max_workers,
    description="Hospup Video Processing Infrastructure - ECS Fargate FFmpeg with Warm Pool"
)

# Tags pour organisation et billing
Tags.of(stack).add("Project", "Hospup")
Tags.of(stack).add("Environment", "Production")
Tags.of(stack).add("ManagedBy", "CDK")
Tags.of(stack).add("Component", "VideoProcessing")

app.synth()

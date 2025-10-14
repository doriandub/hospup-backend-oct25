"""
🎬 Hospup Video Processing Stack
Infrastructure complète pour génération vidéo avec FFmpeg sur ECS Fargate
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_ecr as ecr,
    aws_sqs as sqs,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_logs as logs,
    aws_applicationautoscaling as appscaling,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct


class VideoProcessingStack(Stack):
    """
    Stack CDK pour infrastructure vidéo scalable avec warm pool
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        warm_pool_size: int = 10,
        max_workers: int = 50,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.warm_pool_size = warm_pool_size
        self.max_workers = max_workers

        # 1. ECR Repository pour image Docker FFmpeg
        self.create_ecr_repository()

        # 2. SQS Queue pour jobs vidéo
        self.create_sqs_queue()

        # 3. VPC (utilise default VPC)
        self.setup_vpc()

        # 4. ECS Cluster
        self.create_ecs_cluster()

        # 5. Task Definition avec IAM roles
        self.create_task_definition()

        # 6. ECS Service avec warm pool
        self.create_ecs_service()

        # 7. Autoscaling basé sur SQS
        self.setup_autoscaling()

        # 8. CloudWatch Dashboard
        self.create_dashboard()

        # 9. Outputs
        self.create_outputs()

    def create_ecr_repository(self):
        """Créer ECR repository pour image Docker FFmpeg"""
        self.ecr_repo = ecr.Repository(
            self,
            "FFmpegWorkerRepository",
            repository_name="hospup-ffmpeg-worker",
            removal_policy=RemovalPolicy.RETAIN,  # Garder les images en cas de destroy
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10
                )
            ]
        )

    def create_sqs_queue(self):
        """Créer SQS queue pour jobs vidéo"""
        # Dead Letter Queue pour messages en erreur
        self.dlq = sqs.Queue(
            self,
            "VideoJobsDLQ",
            queue_name="hospup-video-jobs-dlq",
            retention_period=Duration.days(14)
        )

        # Main queue
        self.queue = sqs.Queue(
            self,
            "VideoJobsQueue",
            queue_name="hospup-video-jobs",
            visibility_timeout=Duration.minutes(15),  # Temps max pour traiter 1 vidéo
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,  # 3 tentatives avant DLQ
                queue=self.dlq
            )
        )

    def setup_vpc(self):
        """Récupérer le VPC par défaut"""
        self.vpc = ec2.Vpc.from_lookup(
            self,
            "DefaultVPC",
            is_default=True
        )

    def create_ecs_cluster(self):
        """Créer ECS Cluster"""
        self.cluster = ecs.Cluster(
            self,
            "VideoProcessingCluster",
            cluster_name="hospup-video-processing",
            vpc=self.vpc,
            container_insights=True  # Activer métriques détaillées
        )

    def create_task_definition(self):
        """Créer Task Definition avec IAM roles"""

        # Task Execution Role (pour ECS lui-même)
        self.execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ]
        )

        # Task Role (pour le worker FFmpeg)
        self.task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Permissions S3
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket"
                ],
                resources=[
                    "arn:aws:s3:::hospup-files",
                    "arn:aws:s3:::hospup-files/*"
                ]
            )
        )

        # Permissions SQS
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes"
                ],
                resources=[self.queue.queue_arn]
            )
        )

        # Task Definition
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "FFmpegWorkerTask",
            family="hospup-ffmpeg-worker",
            cpu=2048,  # 2 vCPU
            memory_limit_mib=4096,  # 4 GB RAM
            execution_role=self.execution_role,
            task_role=self.task_role
        )

        # Log Group
        self.log_group = logs.LogGroup(
            self,
            "WorkerLogGroup",
            log_group_name="/ecs/hospup-ffmpeg-worker",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Container
        self.container = self.task_definition.add_container(
            "ffmpeg-worker",
            image=ecs.ContainerImage.from_ecr_repository(
                self.ecr_repo,
                tag="latest"
            ),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="worker",
                log_group=self.log_group
            ),
            environment={
                "AWS_DEFAULT_REGION": self.region,
                "SQS_QUEUE_URL": self.queue.queue_url,
                "WEBHOOK_URL": "https://hospup-backend-production.up.railway.app/api/v1/videos/ffmpeg-callback"
            }
        )

    def create_ecs_service(self):
        """Créer ECS Service avec Fargate Spot (70% moins cher)"""
        self.service = ecs.FargateService(
            self,
            "FFmpegWorkerService",
            service_name="ffmpeg-worker-service",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=self.warm_pool_size,  # Warm pool initial
            min_healthy_percent=90,  # Permet rolling updates
            max_healthy_percent=200,
            assign_public_ip=True,  # Nécessaire pour accès Internet (ECR, S3)
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT",
                    weight=1,
                    base=0
                )
            ]
        )

    def setup_autoscaling(self):
        """Configurer autoscaling basé sur SQS"""

        # Enable autoscaling
        scaling = self.service.auto_scale_task_count(
            min_capacity=self.warm_pool_size,
            max_capacity=self.max_workers
        )

        # Scale sur nombre de messages SQS
        # Formule: desired_workers = warm_pool + ceil(messages / target_messages_per_worker)
        scaling.scale_on_metric(
            "SQSScaling",
            metric=self.queue.metric_approximate_number_of_messages_visible(),
            scaling_steps=[
                appscaling.ScalingInterval(upper=0, change=-1),  # Scale down si queue vide
                appscaling.ScalingInterval(lower=1, change=+1),  # +1 worker par message
                appscaling.ScalingInterval(lower=10, change=+5), # +5 workers si >10 messages
                appscaling.ScalingInterval(lower=30, change=+10) # +10 workers si >30 messages
            ],
            cooldown=Duration.seconds(30),  # Attendre 30s avant nouveau scale out
            adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY
        )

        # Scale sur CPU (backup)
        scaling.scale_on_cpu_utilization(
            "CPUScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.seconds(30)
        )

    def create_dashboard(self):
        """Créer CloudWatch Dashboard pour monitoring"""
        self.dashboard = cloudwatch.Dashboard(
            self,
            "VideoDashboard",
            dashboard_name="HospupVideoProcessing"
        )

        # Widgets
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="SQS Queue Depth",
                left=[
                    self.queue.metric_approximate_number_of_messages_visible(),
                    self.queue.metric_number_of_messages_received(),
                    self.queue.metric_number_of_messages_deleted()
                ]
            ),
            cloudwatch.GraphWidget(
                title="Dead Letter Queue",
                left=[
                    self.dlq.metric_approximate_number_of_messages_visible()
                ]
            )
        )

    def create_outputs(self):
        """Créer CloudFormation outputs"""

        CfnOutput(
            self,
            "ECRRepositoryURI",
            value=self.ecr_repo.repository_uri,
            description="ECR Repository URI pour pusher l'image Docker",
            export_name="HospupECRRepositoryURI"
        )

        CfnOutput(
            self,
            "SQSQueueURL",
            value=self.queue.queue_url,
            description="SQS Queue URL pour envoyer les jobs vidéo",
            export_name="HospupSQSQueueURL"
        )

        CfnOutput(
            self,
            "SQSQueueARN",
            value=self.queue.queue_arn,
            description="SQS Queue ARN",
            export_name="HospupSQSQueueARN"
        )

        CfnOutput(
            self,
            "ECSClusterName",
            value=self.cluster.cluster_name,
            description="ECS Cluster Name",
            export_name="HospupECSClusterName"
        )

        CfnOutput(
            self,
            "ECSServiceName",
            value=self.service.service_name,
            description="ECS Service Name",
            export_name="HospupECSServiceName"
        )

        CfnOutput(
            self,
            "WarmPoolSize",
            value=str(self.warm_pool_size),
            description="Nombre de workers toujours actifs (warm pool)"
        )

        CfnOutput(
            self,
            "MaxWorkers",
            value=str(self.max_workers),
            description="Nombre maximum de workers (autoscaling)"
        )

        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={self.dashboard.dashboard_name}",
            description="CloudWatch Dashboard URL"
        )

        CfnOutput(
            self,
            "LogGroupName",
            value=self.log_group.log_group_name,
            description="CloudWatch Log Group pour worker logs"
        )

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
import structlog

logger = structlog.get_logger(__name__)

# Supabase PostgreSQL connection configuration
raw_db_url = settings.DATABASE_URL

if "pooler.supabase.com" in raw_db_url or True:  # Force Supabase pooler path
    # Direct Supabase pooler configuration
    username = "postgres.vvyhkjwymytnowsiwajm"
    password = ".mvR66vs7YGQXJ%23"  # URL encoded # as %23
    hostname = "aws-1-eu-west-1.pooler.supabase.com"
    port = 5432  # Session pooler port
    database = "postgres"
    
    # Construct clean SQLAlchemy URL
    sqlalchemy_url = f"postgresql+asyncpg://{username}:{password}@{hostname}:{port}/{database}"
    
    logger.info("Supabase pooler connection configured", hostname=hostname, port=port)
else:
    # Standard URL transformation (fallback)
    sqlalchemy_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://")
    logger.info("Standard database connection configured")

# Create async engine with enhanced timeout and connection settings
engine = create_async_engine(
    sqlalchemy_url,
    echo=False,
    pool_size=5,  # Reduced pool size for better connection management
    max_overflow=10,  # Reduced overflow
    pool_pre_ping=True,
    pool_recycle=300,  # 5 minutes
    pool_timeout=30,  # 30 seconds to get connection from pool
    connect_args={
        "command_timeout": 60,  # Command timeout: 60 seconds
        "server_settings": {
            "application_name": "hospup_backend",
            "jit": "off",  # Disable JIT for faster connection
        },
    },
)

# Create sync engine for Celery tasks
sync_sqlalchemy_url = sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
sync_engine = create_engine(
    sync_sqlalchemy_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30
)

# Create session factories
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
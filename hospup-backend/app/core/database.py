from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from .config import settings
import structlog

# Create declarative base for models
Base = declarative_base()

logger = structlog.get_logger(__name__)

# Supabase PostgreSQL connection configuration
raw_db_url = settings.DATABASE_URL

if "pooler.supabase.com" in raw_db_url or True:  # Force Supabase pooler path
    # Direct Supabase pooler configuration  
    # Remove pgbouncer param that causes SQLAlchemy issues
    clean_url = raw_db_url.split('?')[0] if '?' in raw_db_url else raw_db_url
    username = "postgres.vvyhkjwymytnowsiwajm"
    password = ".mvR66vs7YGQXJ%23"  # URL encoded # as %23
    hostname = "aws-1-eu-west-1.pooler.supabase.com"
    port = 5432  # Session pooler port - use 5432 not 6543 for better compatibility
    database = "postgres"
    
    # Construct clean SQLAlchemy URL
    sqlalchemy_url = f"postgresql+asyncpg://{username}:{password}@{hostname}:{port}/{database}"
    
    logger.info("Supabase pooler connection configured", hostname=hostname, port=port)
else:
    # Standard URL transformation (fallback)
    sqlalchemy_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://")
    logger.info("Standard database connection configured")

# Create async engine optimized for Supabase cloud limits
engine = create_async_engine(
    sqlalchemy_url,
    echo=False,
    pool_size=1,  # Minimal pool size for Supabase free tier
    max_overflow=1,  # Minimal overflow to respect connection limits
    pool_pre_ping=True,
    pool_recycle=180,  # 3 minutes - faster recycling
    pool_timeout=10,  # Shorter timeout to fail fast
    connect_args={
        "command_timeout": 30,  # Shorter command timeout
        "server_settings": {
            "application_name": "hospup_cloud_backend",
            "jit": "off",  # Disable JIT for faster connection
        },
    },
)

# Create sync engine for template operations
if "pooler.supabase.com" in raw_db_url or True:
    sync_sqlalchemy_url = f"postgresql+psycopg2://{username}:{password}@{hostname}:{port}/{database}"
else:
    sync_sqlalchemy_url = sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

sync_engine = create_engine(
    sync_sqlalchemy_url,
    echo=False,
    pool_size=1,  # Minimal pool size for Supabase cloud limits
    max_overflow=1,  # Minimal overflow
    pool_pre_ping=True,
    pool_recycle=180,  # 3 minutes - faster recycling
    pool_timeout=10  # Shorter timeout to fail fast
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

def get_sync_db() -> Session:
    """Dependency to get sync database session"""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
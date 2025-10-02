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

    # SECURITY: Use environment variables for credentials
    username = settings.DB_USERNAME
    password = settings.DB_PASSWORD
    hostname = settings.DB_HOSTNAME
    port = settings.DB_PORT or 6543  # Transaction pooler port
    database = settings.DB_NAME or "postgres"

    # Construct clean SQLAlchemy URL
    sqlalchemy_url = f"postgresql+asyncpg://{username}:{password}@{hostname}:{port}/{database}"

    logger.info("Supabase transaction pooler connection configured", hostname=hostname, port=port)
else:
    # Standard URL transformation (fallback)
    sqlalchemy_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://")
    logger.info("Standard database connection configured")

# Create async engine optimized for Supabase cloud limits
engine = create_async_engine(
    sqlalchemy_url,
    echo=False,
    pool_size=2,  # Conservative pool size for Supabase transaction mode
    max_overflow=3,  # Conservative overflow
    pool_pre_ping=True,
    pool_recycle=180,  # 3 minutes - faster recycling
    pool_timeout=30,  # Increased timeout for better reliability
    pool_reset_on_return='rollback',  # Always rollback to clean state
    connect_args={
        "command_timeout": 30,  # Shorter command timeout
        "prepared_statement_cache_size": 0,  # Disable problematic prepared statements
        "statement_cache_size": 0,  # Disable statement cache
        "server_settings": {
            "application_name": "hospup_cloud_backend",
            "jit": "off",  # Disable JIT for faster connection
        },
        # Fix DuplicatePreparedStatementError by disabling prepared statements
        "prepared_statement_cache_size": 0,
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
    pool_size=2,  # Conservative pool size for Supabase transaction mode
    max_overflow=3,  # Conservative overflow
    pool_pre_ping=True,
    pool_recycle=180,  # 3 minutes - faster recycling
    pool_timeout=30  # Increased timeout for better reliability
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
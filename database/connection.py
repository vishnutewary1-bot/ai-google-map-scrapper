"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from contextlib import contextmanager
from config.settings import settings
from database.models import Base
from loguru import logger


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Initialize database connection with proper connection pooling."""
        try:
            import os
            # Create data directory for SQLite if needed
            if settings.db_type.lower() == "sqlite":
                os.makedirs("data", exist_ok=True)
                # SQLite doesn't support connection pooling in the same way
                self.engine = create_engine(
                    settings.database_url,
                    connect_args={"check_same_thread": False},
                    poolclass=NullPool,  # SQLite works better with NullPool
                    echo=False
                )
            else:
                # PostgreSQL/MySQL with proper connection pooling
                self.engine = create_engine(
                    settings.database_url,
                    poolclass=QueuePool,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_size=5,  # Base pool size
                    max_overflow=10,  # Additional connections when pool is exhausted
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    pool_timeout=30,  # Wait up to 30s for available connection
                    echo=False
                )
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            logger.info(f"Database connection initialized successfully ({settings.db_type})")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_tables(self):
        """Create all tables in the database."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def drop_tables(self):
        """Drop all tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("All database tables dropped")

    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a database session (manual management required)."""
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()

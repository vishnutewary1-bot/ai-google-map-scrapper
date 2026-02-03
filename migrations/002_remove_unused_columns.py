"""Migration: Remove unused database columns and tables.

This migration removes:
1. Columns from business_leads:
   - cid (never extracted or queried)
   - change_history (never populated)
   - social_tiktok (never extracted)
   - social_pinterest (never extracted)
   - social_whatsapp (use whatsapp_number instead)

2. Tables:
   - export_history (incomplete feature)
   - webhook_history (incomplete feature)

Date: 2026-02-03
"""

from sqlalchemy import text
from loguru import logger


def upgrade(engine):
    """Apply migration - remove unused columns and tables."""
    with engine.begin() as conn:
        # Get database type
        dialect = engine.dialect.name

        logger.info("Starting migration: Remove unused columns and tables")

        # Remove columns from business_leads
        columns_to_remove = [
            'cid',
            'change_history',
            'social_tiktok',
            'social_pinterest',
            'social_whatsapp',
        ]

        for column in columns_to_remove:
            try:
                if dialect == 'sqlite':
                    # SQLite doesn't support DROP COLUMN directly in older versions
                    # Check if column exists first
                    result = conn.execute(
                        text("SELECT COUNT(*) FROM pragma_table_info('business_leads') WHERE name = :col"),
                        {"col": column}
                    )
                    if result.scalar() > 0:
                        logger.info(f"Note: SQLite cannot drop column '{column}', it will be ignored")
                else:
                    # PostgreSQL and MySQL support DROP COLUMN
                    conn.execute(text(f"ALTER TABLE business_leads DROP COLUMN IF EXISTS {column}"))
                    logger.info(f"Dropped column: {column}")
            except Exception as e:
                logger.warning(f"Could not drop column {column}: {e}")

        # Drop unused tables
        tables_to_drop = ['export_history', 'webhook_history']

        for table in tables_to_drop:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")

        logger.info("Migration completed: Remove unused columns and tables")


def downgrade(engine):
    """Rollback migration - recreate columns and tables (empty)."""
    with engine.begin() as conn:
        dialect = engine.dialect.name

        logger.info("Rolling back migration: Recreating unused columns and tables")

        # Recreate columns (if not SQLite)
        if dialect != 'sqlite':
            columns_to_add = [
                ('cid', 'VARCHAR(50)'),
                ('change_history', 'JSON'),
                ('social_tiktok', 'VARCHAR(500)'),
                ('social_pinterest', 'VARCHAR(500)'),
                ('social_whatsapp', 'VARCHAR(500)'),
            ]

            for column, col_type in columns_to_add:
                try:
                    conn.execute(text(
                        f"ALTER TABLE business_leads ADD COLUMN IF NOT EXISTS {column} {col_type}"
                    ))
                    logger.info(f"Added column: {column}")
                except Exception as e:
                    logger.warning(f"Could not add column {column}: {e}")

        # Recreate tables (empty)
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS export_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename VARCHAR(500) NOT NULL,
                    format VARCHAR(50) NOT NULL,
                    record_count INTEGER DEFAULT 0,
                    file_size INTEGER,
                    cloud_provider VARCHAR(50),
                    cloud_url VARCHAR(1000),
                    filters JSON,
                    status VARCHAR(50) DEFAULT 'completed',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("Created table: export_history")
        except Exception as e:
            logger.warning(f"Could not create export_history table: {e}")

        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS webhook_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_name VARCHAR(100) NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    url VARCHAR(500),
                    payload JSON,
                    response_status INTEGER,
                    response_body TEXT,
                    success BOOLEAN DEFAULT FALSE,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("Created table: webhook_history")
        except Exception as e:
            logger.warning(f"Could not create webhook_history table: {e}")

        logger.info("Rollback completed")


if __name__ == "__main__":
    # Run migration directly
    from database.connection import db_manager

    db_manager.initialize()
    upgrade(db_manager.engine)

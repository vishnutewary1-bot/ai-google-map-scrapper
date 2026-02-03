"""
Migration: Add star_rating column to business_leads table.

Run this script once after updating the models.py to add the star_rating column
to existing databases.

Usage:
    python migrations/001_add_star_rating.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from database.connection import db_manager
from utils.lead_scoring import score_to_stars
from loguru import logger


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_star_rating_column():
    """Add star_rating column to business_leads table."""
    logger.info("Starting migration: Add star_rating column")

    # Initialize database
    db_manager.initialize()

    # Check if column already exists
    if check_column_exists(db_manager.engine, 'business_leads', 'star_rating'):
        logger.info("Column 'star_rating' already exists. Skipping column creation.")
    else:
        # Add the column
        with db_manager.engine.connect() as conn:
            try:
                conn.execute(text(
                    "ALTER TABLE business_leads ADD COLUMN star_rating INTEGER DEFAULT 0"
                ))
                conn.commit()
                logger.info("Successfully added 'star_rating' column")
            except Exception as e:
                logger.error(f"Error adding column: {e}")
                raise

    # Create index if it doesn't exist
    try:
        with db_manager.engine.connect() as conn:
            # Check for SQLite vs PostgreSQL syntax
            inspector = inspect(db_manager.engine)
            indexes = inspector.get_indexes('business_leads')
            index_names = [idx['name'] for idx in indexes]

            if 'idx_star_rating' not in index_names:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_star_rating ON business_leads (star_rating)"
                ))
                conn.commit()
                logger.info("Successfully created 'idx_star_rating' index")
            else:
                logger.info("Index 'idx_star_rating' already exists")
    except Exception as e:
        logger.warning(f"Could not create index (may already exist): {e}")


def backfill_star_ratings():
    """
    Calculate star ratings for all existing leads based on their lead_score_numeric.
    """
    logger.info("Starting backfill: Calculate star ratings for existing leads")

    db_manager.initialize()

    with db_manager.get_session() as session:
        # Get all leads with a numeric score but no star rating
        result = session.execute(text("""
            SELECT id, lead_score_numeric, data_quality_score
            FROM business_leads
            WHERE star_rating IS NULL OR star_rating = 0
        """))

        leads = result.fetchall()
        logger.info(f"Found {len(leads)} leads to update")

        updated = 0
        for lead_id, lead_score, quality_score in leads:
            # Use lead_score_numeric if available, otherwise use data_quality_score
            score = lead_score or quality_score or 0
            stars = score_to_stars(score)

            session.execute(text(
                "UPDATE business_leads SET star_rating = :stars WHERE id = :id"
            ), {"stars": stars, "id": lead_id})
            updated += 1

            if updated % 100 == 0:
                logger.info(f"Updated {updated} leads...")

        session.commit()
        logger.info(f"Successfully updated star ratings for {updated} leads")


def main():
    """Run the migration."""
    print("=" * 60)
    print("Migration: Add Star Rating Column to Business Leads")
    print("=" * 60)

    try:
        # Step 1: Add the column
        add_star_rating_column()

        # Step 2: Backfill existing data
        backfill_star_ratings()

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

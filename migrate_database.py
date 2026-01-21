"""Database migration script to add new columns for enhanced scraper features."""
import sqlite3
import os
from pathlib import Path


def migrate_database(db_path: str = "data/mapleads.db"):
    """Add new columns to the business_leads table."""

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Run the scraper once to create the database first.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # New columns to add
    new_columns = [
        # Multiple phones
        ("phone_1", "VARCHAR(50)"),
        ("phone_2", "VARCHAR(50)"),
        ("phone_3", "VARCHAR(50)"),

        # Multiple emails
        ("email_1", "VARCHAR(200)"),
        ("email_2", "VARCHAR(200)"),
        ("email_3", "VARCHAR(200)"),

        # Contact persons
        ("contact_name_1", "VARCHAR(200)"),
        ("contact_title_1", "VARCHAR(200)"),
        ("contact_email_1", "VARCHAR(200)"),
        ("contact_name_2", "VARCHAR(200)"),
        ("contact_title_2", "VARCHAR(200)"),
        ("contact_email_2", "VARCHAR(200)"),
        ("contact_name_3", "VARCHAR(200)"),
        ("contact_title_3", "VARCHAR(200)"),
        ("contact_email_3", "VARCHAR(200)"),

        # Additional social media
        ("social_tiktok", "VARCHAR(500)"),
        ("social_pinterest", "VARCHAR(500)"),
        ("social_whatsapp", "VARCHAR(500)"),

        # Company insights
        ("employees", "VARCHAR(100)"),
        ("employees_min", "INTEGER"),
        ("employees_max", "INTEGER"),
        ("founded_year", "INTEGER"),
        ("revenue", "VARCHAR(100)"),
        ("revenue_min", "FLOAT"),
        ("revenue_max", "FLOAT"),
        ("company_type", "VARCHAR(50)"),
        ("industry", "VARCHAR(200)"),
        ("description", "TEXT"),

        # Review breakdown
        ("reviews_1_star", "INTEGER"),
        ("reviews_2_star", "INTEGER"),
        ("reviews_3_star", "INTEGER"),
        ("reviews_4_star", "INTEGER"),
        ("reviews_5_star", "INTEGER"),

        # Additional fields
        ("business_type", "VARCHAR(100)"),
        ("street", "VARCHAR(500)"),
        ("country", "VARCHAR(100)"),
        ("cid", "VARCHAR(50)"),
        ("data_source", "VARCHAR(100) DEFAULT 'google_maps'"),
    ]

    # Get existing columns
    cursor.execute("PRAGMA table_info(business_leads)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    print(f"Existing columns: {len(existing_columns)}")
    print(f"Columns to potentially add: {len(new_columns)}")

    # Add new columns that don't exist
    added_count = 0
    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE business_leads ADD COLUMN {column_name} {column_type}"
                cursor.execute(sql)
                print(f"  + Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"  - Column already exists: {column_name}")
                else:
                    print(f"  ! Error adding {column_name}: {e}")
        else:
            print(f"  - Column already exists: {column_name}")

    # Add new columns to scrape_jobs table
    scrape_job_columns = [
        ("extract_emails", "BOOLEAN DEFAULT 1"),
        ("extract_social", "BOOLEAN DEFAULT 1"),
        ("extract_insights", "BOOLEAN DEFAULT 1"),
        ("use_proxies", "BOOLEAN DEFAULT 0"),
        ("headless_mode", "BOOLEAN DEFAULT 1"),
        ("current_page", "INTEGER DEFAULT 0"),
        ("current_item", "VARCHAR(500)"),
        ("duration_seconds", "INTEGER"),
        ("resume_state", "TEXT"),
    ]

    cursor.execute("PRAGMA table_info(scrape_jobs)")
    existing_job_columns = {row[1] for row in cursor.fetchall()}

    print("\nUpdating scrape_jobs table:")
    for column_name, column_type in scrape_job_columns:
        if column_name not in existing_job_columns:
            try:
                sql = f"ALTER TABLE scrape_jobs ADD COLUMN {column_name} {column_type}"
                cursor.execute(sql)
                print(f"  + Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"  - Column already exists: {column_name}")
                else:
                    print(f"  ! Error adding {column_name}: {e}")
        else:
            print(f"  - Column already exists: {column_name}")

    # Create export_history table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename VARCHAR(500) NOT NULL,
            format VARCHAR(50) NOT NULL,
            record_count INTEGER DEFAULT 0,
            file_size INTEGER,
            filters TEXT,
            status VARCHAR(50) DEFAULT 'completed',
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("\n+ Ensured export_history table exists")

    # Create indexes for new columns
    print("\nCreating indexes for new columns:")
    indexes = [
        ("idx_email_1", "business_leads", "email_1"),
        ("idx_founded_year", "business_leads", "founded_year"),
        ("idx_employees", "business_leads", "employees"),
        ("idx_revenue", "business_leads", "revenue"),
        ("idx_social_facebook", "business_leads", "social_facebook"),
        ("idx_social_instagram", "business_leads", "social_instagram"),
        ("idx_social_linkedin", "business_leads", "social_linkedin"),
    ]

    for idx_name, table, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
            print(f"  + Created index: {idx_name}")
        except sqlite3.OperationalError as e:
            print(f"  - Index error for {idx_name}: {e}")

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"Migration complete! Added {added_count} new columns.")
    print("Your database is now ready for enhanced scraping features.")
    print(f"{'='*50}")


def check_database_schema(db_path: str = "data/mapleads.db"):
    """Print current database schema for debugging."""
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== BUSINESS_LEADS TABLE ===")
    cursor.execute("PRAGMA table_info(business_leads)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]:30} {col[2]:15} {'NOT NULL' if col[3] else ''}")

    print(f"\nTotal columns: {len(columns)}")

    print("\n=== SCRAPE_JOBS TABLE ===")
    cursor.execute("PRAGMA table_info(scrape_jobs)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]:30} {col[2]:15} {'NOT NULL' if col[3] else ''}")

    print(f"\nTotal columns: {len(columns)}")

    # Check for export_history table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='export_history'")
    if cursor.fetchone():
        print("\n=== EXPORT_HISTORY TABLE ===")
        cursor.execute("PRAGMA table_info(export_history)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]:30} {col[2]:15} {'NOT NULL' if col[3] else ''}")
        print(f"\nTotal columns: {len(columns)}")
    else:
        print("\n! export_history table does not exist")

    conn.close()


if __name__ == "__main__":
    import sys

    db_path = "data/mapleads.db"

    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_database_schema(db_path)
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python migrate_database.py          - Run migration")
            print("  python migrate_database.py --check  - Check current schema")
            print("  python migrate_database.py --help   - Show this help")
        else:
            db_path = sys.argv[1]
            migrate_database(db_path)
    else:
        migrate_database(db_path)

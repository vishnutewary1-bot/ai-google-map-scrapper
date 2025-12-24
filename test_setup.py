"""Test script to verify installation and setup."""
import sys
from loguru import logger


def test_python_version():
    """Test Python version."""
    logger.info("Testing Python version...")
    version = sys.version_info

    if version.major >= 3 and version.minor >= 11:
        logger.success(f"✓ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        logger.error(f"✗ Python {version.major}.{version.minor}.{version.micro} - Need 3.11+")
        return False


def test_imports():
    """Test required package imports."""
    logger.info("Testing package imports...")

    packages = [
        ("playwright", "Playwright"),
        ("psycopg2", "PostgreSQL driver"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("loguru", "Loguru"),
        ("pandas", "Pandas"),
    ]

    all_ok = True
    for package, name in packages:
        try:
            __import__(package)
            logger.success(f"✓ {name} - OK")
        except ImportError:
            logger.error(f"✗ {name} - NOT FOUND")
            all_ok = False

    return all_ok


def test_playwright_browsers():
    """Test Playwright browser installation."""
    logger.info("Testing Playwright browsers...")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Check if chromium is installed
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                logger.success("✓ Playwright Chromium browser - OK")
                return True
            except Exception as e:
                logger.error(f"✗ Playwright Chromium browser - NOT INSTALLED")
                logger.info("Run: playwright install chromium")
                return False

    except Exception as e:
        logger.error(f"✗ Playwright - ERROR: {e}")
        return False


def test_database_connection():
    """Test PostgreSQL database connection."""
    logger.info("Testing database connection...")

    try:
        from config.settings import settings
        from sqlalchemy import create_engine

        engine = create_engine(settings.database_url)
        connection = engine.connect()
        connection.close()

        logger.success(f"✓ PostgreSQL connection - OK")
        logger.info(f"  Database: {settings.db_name}")
        logger.info(f"  Host: {settings.db_host}:{settings.db_port}")
        return True

    except Exception as e:
        logger.error(f"✗ PostgreSQL connection - FAILED")
        logger.error(f"  Error: {e}")
        logger.info("  Check your .env file and ensure PostgreSQL is running")
        return False


def test_database_tables():
    """Test if database tables exist."""
    logger.info("Testing database tables...")

    try:
        from database import db_manager, BusinessLead, ScrapeJob

        db_manager.initialize()

        with db_manager.get_session() as session:
            # Try to query tables
            session.query(BusinessLead).count()
            session.query(ScrapeJob).count()

        logger.success("✓ Database tables - OK")
        return True

    except Exception as e:
        logger.warning(f"⚠ Database tables not found or error: {e}")
        logger.info("  Run: python main.py init-db")
        return False


def test_directories():
    """Test if required directories exist."""
    logger.info("Testing directories...")

    from pathlib import Path

    dirs = ["logs", "exports"]
    all_ok = True

    for dir_name in dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            logger.success(f"✓ {dir_name}/ directory - OK")
        else:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ {dir_name}/ directory - CREATED")

    return all_ok


def test_config():
    """Test configuration loading."""
    logger.info("Testing configuration...")

    try:
        from config.settings import settings

        logger.success("✓ Configuration loaded - OK")
        logger.info(f"  Headless mode: {settings.headless_mode}")
        logger.info(f"  Max results per search: {settings.max_results_per_search}")
        logger.info(f"  Delay between requests: {settings.delay_between_requests_min}-{settings.delay_between_requests_max}s")
        return True

    except Exception as e:
        logger.error(f"✗ Configuration - ERROR: {e}")
        logger.info("  Check your .env file")
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Google Maps Scraper - Setup Test")
    logger.info("=" * 60)
    logger.info("")

    results = []

    # Run tests
    results.append(("Python Version", test_python_version()))
    logger.info("")

    results.append(("Package Imports", test_imports()))
    logger.info("")

    results.append(("Playwright Browsers", test_playwright_browsers()))
    logger.info("")

    results.append(("Configuration", test_config()))
    logger.info("")

    results.append(("Directories", test_directories()))
    logger.info("")

    results.append(("Database Connection", test_database_connection()))
    logger.info("")

    results.append(("Database Tables", test_database_tables()))
    logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name:25} {status}")

    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")

    if passed == total:
        logger.success("=" * 60)
        logger.success("ALL TESTS PASSED! 🎉")
        logger.success("You're ready to start scraping!")
        logger.success("=" * 60)
        logger.info("")
        logger.info("Try your first scrape:")
        logger.info('  python main.py scrape --query "coffee shops" --location "Mumbai" --limit 10')
        return True
    else:
        logger.error("=" * 60)
        logger.error("SOME TESTS FAILED")
        logger.error("Please fix the issues above before proceeding")
        logger.error("=" * 60)
        logger.info("")
        logger.info("Common fixes:")
        logger.info("  1. Install missing packages: pip install -r requirements.txt")
        logger.info("  2. Install Playwright browsers: playwright install chromium")
        logger.info("  3. Create .env file from .env.example and configure database")
        logger.info("  4. Initialize database: python main.py init-db")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

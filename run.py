"""Start the MapLeads Pro server v2.0."""
import os
import sys

# Change to the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add current directory to path
sys.path.insert(0, os.getcwd())


def main():
    """Main entry point."""
    import uvicorn
    from loguru import logger

    print("=" * 60)
    print("  MapLeads Pro v2.0 - Google Maps Lead Scraper")
    print("  Unified Edition with Full Enrichment")
    print("=" * 60)

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/server.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )

    # Initialize database
    print("\n[1/3] Initializing database...")
    try:
        from database import db_manager
        db_manager.initialize()
        db_manager.create_tables()
        print("      Database initialized successfully!")
    except Exception as e:
        print(f"      Warning: Database initialization failed: {e}")
        print("      The API will run but database features will be limited.")

    # Check Playwright browsers
    print("\n[2/3] Checking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("      Playwright browsers are ready!")
    except Exception as e:
        print("      Warning: Playwright browsers not available.")
        print("      Run: playwright install chromium")
        print(f"      Error: {e}")

    # Create exports directory
    os.makedirs("exports", exist_ok=True)

    # Start server
    print("\n[3/3] Starting FastAPI server...")
    print("\n" + "=" * 60)
    print("  Frontend:  http://localhost:9000/app")
    print("  API Docs:  http://localhost:9000/api/docs")
    print("  Health:    http://localhost:9000/api/health")
    print("  WebSocket: ws://localhost:9000/ws")
    print("=" * 60 + "\n")

    # Use the new modular API
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()

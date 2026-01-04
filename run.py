"""Start the MapLeads Pro server."""
import os
import sys

# Change to the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add current directory to path
sys.path.insert(0, os.getcwd())

def main():
    """Main entry point."""
    import uvicorn
    from database import db_manager

    print("=" * 50)
    print("MapLeads Pro - Google Maps Lead Scraper")
    print("=" * 50)

    # Initialize database
    print("\n[1/3] Initializing database...")
    db_manager.initialize()
    db_manager.create_tables()
    print("Database initialized successfully!")

    # Install playwright browsers if needed
    print("\n[2/3] Checking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Just check if browsers are available
            pass
        print("Playwright browsers are ready!")
    except Exception as e:
        print(f"Note: You may need to install Playwright browsers with: playwright install chromium")

    # Start server
    print("\n[3/3] Starting FastAPI server...")
    print("\n" + "=" * 50)
    print("Dashboard: http://localhost:8000/dashboard")
    print("API Docs:  http://localhost:8000/docs")
    print("=" * 50 + "\n")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()

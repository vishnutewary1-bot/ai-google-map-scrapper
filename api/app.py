"""FastAPI application factory."""

import os
import sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import text
from loguru import logger

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.middleware import setup_middleware
from api.routes import (
    scraping_router,
    leads_router,
    export_router,
    analytics_router,
    websocket_router,
    features_router,
    settings_router,
)
from api.schemas.responses import HealthResponse

# Database initialization
try:
    from database import db_manager
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="AI Google Maps Scraper",
        description="Advanced lead generation from Google Maps with enrichment capabilities",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Setup middleware (CORS, logging, error handling)
    setup_middleware(app)

    # Include routers
    app.include_router(scraping_router, prefix="/api", tags=["Scraping"])
    app.include_router(leads_router, prefix="/api", tags=["Leads"])
    app.include_router(export_router, prefix="/api", tags=["Export"])
    app.include_router(analytics_router, prefix="/api", tags=["Analytics"])
    app.include_router(websocket_router, tags=["WebSocket"])
    app.include_router(features_router, prefix="/api", tags=["Features"])
    app.include_router(settings_router, prefix="/api", tags=["Settings"])

    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Check API health status."""
        db_status = "connected"
        if HAS_DATABASE:
            try:
                with db_manager.get_session() as session:
                    session.execute(text("SELECT 1"))
            except Exception:
                db_status = "disconnected"
        else:
            db_status = "not configured"

        return HealthResponse(
            status="healthy",
            version="2.0.0",
            database=db_status,
            timestamp=datetime.utcnow(),
        )

    # Serve static frontend files if they exist
    frontend_path = Path(__file__).parent.parent / "frontend"
    if frontend_path.exists():
        from fastapi.responses import FileResponse, RedirectResponse

        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            """Serve frontend index.html."""
            return FileResponse(frontend_path / "index.html")

        @app.get("/app", include_in_schema=False)
        async def serve_app():
            """Serve frontend at /app route."""
            return FileResponse(frontend_path / "index.html")

        @app.get("/app.js", include_in_schema=False)
        async def serve_js():
            """Serve frontend JavaScript."""
            return FileResponse(frontend_path / "app.js", media_type="application/javascript")

        # Mount static files for any other assets
        app.mount(
            "/static",
            StaticFiles(directory=str(frontend_path)),
            name="static"
        )
        logger.info(f"Serving frontend from {frontend_path}")
    else:
        # Fallback if no frontend
        @app.get("/", include_in_schema=False)
        async def root():
            """API info."""
            return JSONResponse({
                "message": "AI Google Maps Scraper API v2.0.0",
                "docs": "/api/docs",
                "health": "/api/health",
            })

    # Startup event
    @app.on_event("startup")
    async def startup_event():
        """Initialize resources on startup."""
        logger.info("Starting AI Google Maps Scraper API v2.0.0")

        # Initialize database
        if HAS_DATABASE:
            try:
                db_manager.initialize()
                db_manager.create_tables()
                logger.info("Database initialized")
            except Exception as e:
                logger.error(f"Database initialization failed: {e}")

        # Create exports directory
        os.makedirs("exports", exist_ok=True)

    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup resources on shutdown."""
        logger.info("Shutting down API...")

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        "logs/api.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )

    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

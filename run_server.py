#!/usr/bin/env python3
"""
MapLeads Pro v2.0 - Server Launcher
Run this file to start the server on localhost:9000
"""

import os
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

# Create necessary directories
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("exports", exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    from loguru import logger

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        "logs/server.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )

    logger.info("=" * 60)
    logger.info("MapLeads Pro v2.0 - Google Maps Lead Scraper")
    logger.info("=" * 60)
    logger.info("Starting server on http://localhost:9000")
    logger.info("API Documentation: http://localhost:9000/api/docs")
    logger.info("Dashboard: http://localhost:9000/")
    logger.info("=" * 60)

    # Run server
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
        reload_dirs=["api", "scraper", "utils", "database", "config"],
    )

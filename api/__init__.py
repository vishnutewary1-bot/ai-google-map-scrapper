"""
API Package v2.0.0

Modular FastAPI backend for the Google Maps Scraper.

Structure:
- app.py: FastAPI application factory
- middleware.py: CORS, logging, error handling
- routes/: API endpoint handlers
- services/: Business logic layer
- schemas/: Pydantic request/response models
"""

from .app import app, create_app

__version__ = "2.0.0"

__all__ = [
    "app",
    "create_app",
]

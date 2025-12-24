"""Vercel serverless entry point for FastAPI."""
from api.main import app

# Vercel requires the app to be named 'app' or exported
# This file serves as the entry point for Vercel
handler = app

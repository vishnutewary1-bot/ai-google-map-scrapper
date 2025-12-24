"""Logging configuration for the application."""
from loguru import logger
import sys
from pathlib import Path
from config.settings import settings


def setup_logger():
    """Configure loguru logger with file and console output."""
    # Remove default logger
    logger.remove()

    # Create logs directory
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Console output (colorized)
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )

    # File output (detailed with rotation)
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )

    logger.info("Logger initialized successfully")


# Initialize logger when module is imported
setup_logger()

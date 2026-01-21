"""Logging configuration for the application."""
from loguru import logger
import sys
import re
from pathlib import Path
from config.settings import settings


def sanitize_log(message: str) -> str:
    """Remove sensitive data from log messages."""
    if not isinstance(message, str):
        message = str(message)

    # Remove email addresses
    message = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', message)

    # Remove phone numbers (various formats)
    message = re.sub(r'\+?[\d\s\-\(\)]{10,}', '[PHONE]', message)

    # Remove API keys, tokens, passwords, secrets
    message = re.sub(
        r'(api_key|token|password|secret|authorization|bearer|api-key|apikey)["\']?\s*[:=]\s*["\']?[\w\-\.]+',
        r'\1=[REDACTED]',
        message,
        flags=re.IGNORECASE
    )

    # Remove credit card numbers (basic pattern)
    message = re.sub(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', '[CARD]', message)

    # Remove IP addresses
    message = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', message)

    return message


def sanitize_filter(record):
    """Loguru filter to sanitize all log messages."""
    record["message"] = sanitize_log(record["message"])
    return True


def setup_logger():
    """Configure loguru logger with file and console output."""
    # Remove default logger
    logger.remove()

    # Create logs directory
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Console output (colorized) with sanitization filter
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        filter=sanitize_filter
    )

    # File output (detailed with rotation) with sanitization filter
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        filter=sanitize_filter
    )

    logger.info("Logger initialized successfully")


# Initialize logger when module is imported
setup_logger()

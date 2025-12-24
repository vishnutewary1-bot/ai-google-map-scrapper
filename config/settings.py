"""Configuration settings for Google Maps Scraper."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "mapleads"
    db_user: str = "postgres"
    db_password: str = ""

    # Scraper Configuration
    max_results_per_search: int = 100
    delay_between_requests_min: int = 3
    delay_between_requests_max: int = 8
    headless_mode: bool = True
    browser_timeout: int = 60000

    # Rate Limiting
    max_requests_per_hour: int = 100
    cooldown_after_detection: int = 1800

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/scraper.log"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

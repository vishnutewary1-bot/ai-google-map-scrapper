"""Configuration settings for Google Maps Scraper."""
from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    db_type: str = "sqlite"  # 'sqlite' or 'postgresql'
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

    # ==================== NEW FEATURES CONFIGURATION ====================

    # CAPTCHA Solving (2Captcha)
    captcha_api_key: Optional[str] = None
    captcha_enabled: bool = False

    # Google Sheets Integration
    google_credentials_path: str = "config/google_credentials.json"
    google_sheets_enabled: bool = False

    # Webhook Notifications
    slack_token: Optional[str] = None
    slack_channel: Optional[str] = None
    discord_webhook_url: Optional[str] = None

    # Email Notifications
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None  # Comma-separated list

    # CRM Integrations
    hubspot_access_token: Optional[str] = None
    salesforce_username: Optional[str] = None
    salesforce_password: Optional[str] = None
    salesforce_security_token: Optional[str] = None
    salesforce_domain: str = "login"

    # Airtable Integration
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # Notion Integration
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None

    # AI Features
    openai_api_key: Optional[str] = None
    ai_lead_scoring_enabled: bool = False

    # Email Verification
    email_verification_api_key: Optional[str] = None
    email_verification_provider: str = "abstract"  # abstract, hunter, neverbounce

    # Scheduling
    scheduler_enabled: bool = False
    scheduler_timezone: str = "UTC"

    # Authentication (for multi-user)
    auth_enabled: bool = False
    jwt_secret_key: str = "your-super-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    @property
    def database_url(self) -> str:
        """Construct database URL based on db_type."""
        if self.db_type.lower() == "sqlite":
            return f"sqlite:///data/{self.db_name}.db"
        else:
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def email_recipients(self) -> List[str]:
        """Get list of email recipients."""
        if self.email_to:
            return [e.strip() for e in self.email_to.split(",")]
        return []

    def get_integrations_status(self) -> dict:
        """Get status of all integrations."""
        return {
            "captcha": {
                "enabled": self.captcha_enabled,
                "configured": bool(self.captcha_api_key)
            },
            "google_sheets": {
                "enabled": self.google_sheets_enabled,
                "configured": os.path.exists(self.google_credentials_path)
            },
            "slack": {
                "configured": bool(self.slack_token and self.slack_channel)
            },
            "discord": {
                "configured": bool(self.discord_webhook_url)
            },
            "email": {
                "configured": bool(self.smtp_host and self.smtp_user)
            },
            "hubspot": {
                "configured": bool(self.hubspot_access_token)
            },
            "salesforce": {
                "configured": bool(self.salesforce_username and self.salesforce_password)
            },
            "airtable": {
                "configured": bool(self.airtable_api_key)
            },
            "notion": {
                "configured": bool(self.notion_api_key)
            },
            "ai_scoring": {
                "enabled": self.ai_lead_scoring_enabled,
                "configured": bool(self.openai_api_key)
            },
            "email_verification": {
                "configured": bool(self.email_verification_api_key)
            },
            "scheduler": {
                "enabled": self.scheduler_enabled
            },
            "auth": {
                "enabled": self.auth_enabled
            }
        }

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

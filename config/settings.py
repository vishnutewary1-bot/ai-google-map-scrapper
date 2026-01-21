"""Configuration settings for Google Maps Scraper - Enhanced version with all features."""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List
import os
import warnings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==================== DATABASE CONFIGURATION ====================
    db_type: str = "sqlite"  # 'sqlite' or 'postgresql'
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "mapleads"
    db_user: str = "postgres"
    db_password: str = ""

    # ==================== SCRAPER CONFIGURATION ====================
    max_results_per_search: int = 100
    delay_between_requests_min: int = 3
    delay_between_requests_max: int = 8
    headless_mode: bool = True
    browser_timeout: int = 60000

    # ==================== GEOLOCATION CONFIGURATION ====================
    geo_latitude: float = 19.0760  # Default: Mumbai
    geo_longitude: float = 72.8777
    geo_timezone: str = "Asia/Kolkata"
    geo_locale: str = "en-US"

    # ==================== RATE LIMITING ====================
    max_requests_per_hour: int = 100
    cooldown_after_detection: int = 1800

    # ==================== LOGGING ====================
    log_level: str = "INFO"
    log_file: str = "logs/scraper.log"

    # ==================== PROXY MANAGER CONFIGURATION ====================
    use_proxy_manager: bool = False
    proxy_refresh_interval: int = 3600  # Refresh proxies every hour
    proxy_test_count: int = 20  # Number of proxies to test
    proxy_test_timeout: int = 10  # Timeout for proxy testing
    custom_proxy_list: Optional[str] = None  # Comma-separated proxy URLs

    # ==================== CAPTCHA SOLVING (2Captcha) ====================
    captcha_api_key: Optional[str] = None
    captcha_enabled: bool = False
    captcha_timeout: int = 120  # Max wait time for captcha solution

    # ==================== GOOGLE SHEETS INTEGRATION ====================
    google_credentials_path: str = "config/google_credentials.json"
    google_sheets_enabled: bool = False

    # ==================== WEBHOOK NOTIFICATIONS ====================
    webhook_url: Optional[str] = None  # Generic webhook URL (Zapier/Make/n8n)
    webhook_secret: Optional[str] = None  # HMAC secret for signing
    webhook_enabled: bool = False
    webhook_events: str = "job.completed,job.failed,lead.created"  # Comma-separated

    # Slack
    slack_token: Optional[str] = None
    slack_channel: Optional[str] = None

    # Discord
    discord_webhook_url: Optional[str] = None

    # ==================== EMAIL NOTIFICATIONS ====================
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None  # Comma-separated list

    # ==================== CRM INTEGRATIONS ====================
    # HubSpot
    hubspot_access_token: Optional[str] = None

    # Salesforce
    salesforce_username: Optional[str] = None
    salesforce_password: Optional[str] = None
    salesforce_security_token: Optional[str] = None
    salesforce_domain: str = "login"

    # Airtable
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # Notion
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None

    # ==================== AI FEATURES ====================
    openai_api_key: Optional[str] = None
    ai_lead_scoring_enabled: bool = False

    # ==================== EMAIL VERIFICATION ====================
    email_verification_api_key: Optional[str] = None
    email_verification_provider: str = "abstract"  # abstract, hunter, neverbounce

    # ==================== SCHEDULING ====================
    scheduler_enabled: bool = False
    scheduler_timezone: str = "UTC"

    # ==================== AUTHENTICATION ====================
    auth_enabled: bool = False
    jwt_secret_key: str = "your-super-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ==================== CORS CONFIGURATION ====================
    cors_origins: List[str] = ["http://localhost:8000", "http://localhost:3000", "http://127.0.0.1:8000", "http://localhost:9000"]

    # ==================== CLOUD STORAGE ====================
    # AWS S3
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket: Optional[str] = None

    # Google Cloud Storage
    gcs_credentials_path: Optional[str] = None
    gcs_bucket: Optional[str] = None

    # ==================== SENTIMENT ANALYSIS ====================
    sentiment_analysis_enabled: bool = True  # Uses TextBlob (free)

    # ==================== DATA FRESHNESS ====================
    data_freshness_threshold_days: int = 30
    auto_refresh_stale_data: bool = False

    # ==================== CHROME EXTENSION ====================
    chrome_extension_enabled: bool = True
    chrome_extension_api_key: Optional[str] = None  # Optional API key for extension auth

    # ==================== EXPORT SETTINGS ====================
    export_directory: str = "exports"
    default_export_format: str = "excel"  # csv, json, excel
    include_photos_in_export: bool = True
    max_photo_urls_per_lead: int = 5

    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v):
        """Warn if using default JWT secret."""
        if v == "your-super-secret-key-change-this-in-production":
            warnings.warn(
                "WARNING: Using default JWT secret key! "
                "Set JWT_SECRET_KEY environment variable for production.",
                UserWarning
            )
        if len(v) < 32:
            warnings.warn(
                "WARNING: JWT secret key should be at least 32 characters for security.",
                UserWarning
            )
        return v

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

    @property
    def webhook_events_list(self) -> List[str]:
        """Get webhook events as list."""
        return [e.strip() for e in self.webhook_events.split(",")]

    @property
    def custom_proxy_list_parsed(self) -> List[str]:
        """Get custom proxy list as list."""
        if self.custom_proxy_list:
            return [p.strip() for p in self.custom_proxy_list.split(",")]
        return []

    def get_integrations_status(self) -> dict:
        """Get status of all integrations."""
        return {
            "captcha": {
                "enabled": self.captcha_enabled,
                "configured": bool(self.captcha_api_key)
            },
            "proxy_manager": {
                "enabled": self.use_proxy_manager
            },
            "google_sheets": {
                "enabled": self.google_sheets_enabled,
                "configured": os.path.exists(self.google_credentials_path)
            },
            "webhooks": {
                "enabled": self.webhook_enabled,
                "configured": bool(self.webhook_url)
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
            },
            "cloud_storage": {
                "s3_configured": bool(self.aws_access_key and self.s3_bucket),
                "gcs_configured": bool(self.gcs_credentials_path and self.gcs_bucket)
            },
            "sentiment_analysis": {
                "enabled": self.sentiment_analysis_enabled
            },
            "chrome_extension": {
                "enabled": self.chrome_extension_enabled
            }
        }

    def get_new_features_status(self) -> dict:
        """Get status of all new features (v2.0)."""
        return {
            "proxy_manager": {
                "enabled": self.use_proxy_manager,
                "description": "Automatic proxy rotation from free sources"
            },
            "captcha_solver": {
                "enabled": self.captcha_enabled,
                "configured": bool(self.captcha_api_key),
                "description": "2Captcha integration for CAPTCHA solving"
            },
            "webhooks": {
                "enabled": self.webhook_enabled,
                "configured": bool(self.webhook_url),
                "description": "Generic webhooks for Zapier/Make/n8n"
            },
            "cloud_storage": {
                "s3_configured": bool(self.aws_access_key and self.s3_bucket),
                "gcs_configured": bool(self.gcs_credentials_path and self.gcs_bucket),
                "description": "Upload exports to S3 or Google Cloud Storage"
            },
            "sentiment_analysis": {
                "enabled": self.sentiment_analysis_enabled,
                "description": "TextBlob-based review sentiment analysis"
            },
            "chrome_extension": {
                "enabled": self.chrome_extension_enabled,
                "description": "Browser extension for manual extraction"
            },
            "geo_search": {
                "enabled": True,
                "description": "Search by coordinates with radius"
            },
            "bulk_import": {
                "enabled": True,
                "description": "Import from Google Maps URLs"
            },
            "competitor_comparison": {
                "enabled": True,
                "description": "Compare multiple businesses side-by-side"
            },
            "data_freshness": {
                "enabled": True,
                "threshold_days": self.data_freshness_threshold_days,
                "description": "Track when data was last verified"
            },
            "email_templates": {
                "enabled": True,
                "description": "Generate personalized cold emails"
            }
        }

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

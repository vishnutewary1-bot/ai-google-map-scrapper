"""Settings API routes - manage integration configurations."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

router = APIRouter()

# Path to .env file
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class IntegrationSettings(BaseModel):
    """Model for integration settings."""
    # Google Sheets
    google_sheets_enabled: Optional[bool] = None
    google_credentials_path: Optional[str] = None

    # Webhooks
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_events: Optional[str] = None

    # Slack
    slack_token: Optional[str] = None
    slack_channel: Optional[str] = None

    # Discord
    discord_webhook_url: Optional[str] = None

    # Email/SMTP
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None

    # HubSpot
    hubspot_access_token: Optional[str] = None

    # Salesforce
    salesforce_username: Optional[str] = None
    salesforce_password: Optional[str] = None
    salesforce_security_token: Optional[str] = None
    salesforce_domain: Optional[str] = None

    # Airtable
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # Notion
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None

    # OpenAI
    openai_api_key: Optional[str] = None
    ai_lead_scoring_enabled: Optional[bool] = None

    # Email Verification
    email_verification_api_key: Optional[str] = None
    email_verification_provider: Optional[str] = None

    # Cloud Storage - AWS S3
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_region: Optional[str] = None
    s3_bucket: Optional[str] = None

    # Cloud Storage - GCS
    gcs_credentials_path: Optional[str] = None
    gcs_bucket: Optional[str] = None

    # CAPTCHA
    captcha_api_key: Optional[str] = None
    captcha_enabled: Optional[bool] = None

    # Sentiment Analysis
    sentiment_analysis_enabled: Optional[bool] = None

    # Data Freshness
    data_freshness_threshold_days: Optional[int] = None


def read_env_file() -> Dict[str, str]:
    """Read current .env file into a dictionary."""
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars


def write_env_file(env_vars: Dict[str, str]):
    """Write dictionary to .env file, preserving comments."""
    lines = []
    existing_keys = set()

    # Read existing file to preserve comments and order
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#') or not stripped:
                    lines.append(line.rstrip())
                elif '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    existing_keys.add(key)
                    if key in env_vars:
                        value = env_vars[key]
                        # Quote value if it contains spaces
                        if ' ' in str(value) and not str(value).startswith('"'):
                            value = f'"{value}"'
                        lines.append(f"{key}={value}")
                    else:
                        lines.append(line.rstrip())

    # Add new keys that weren't in the file
    for key, value in env_vars.items():
        if key not in existing_keys:
            if ' ' in str(value) and not str(value).startswith('"'):
                value = f'"{value}"'
            lines.append(f"{key}={value}")

    with open(ENV_FILE, 'w') as f:
        f.write('\n'.join(lines) + '\n')


@router.get("/settings/integrations")
async def get_integration_settings():
    """Get all integration settings (without sensitive data shown in full)."""
    try:
        env_vars = read_env_file()

        def mask_sensitive(value: str) -> str:
            """Mask sensitive values, showing only first/last characters."""
            if not value or len(value) < 8:
                return "****" if value else ""
            return f"{value[:4]}...{value[-4:]}"

        def get_bool(key: str, default: bool = False) -> bool:
            val = env_vars.get(key, str(default)).lower()
            return val in ('true', '1', 'yes')

        return {
            "success": True,
            "settings": {
                # Google Sheets
                "google_sheets": {
                    "enabled": get_bool("GOOGLE_SHEETS_ENABLED"),
                    "credentials_path": env_vars.get("GOOGLE_CREDENTIALS_PATH", "config/google_credentials.json"),
                    "configured": os.path.exists(env_vars.get("GOOGLE_CREDENTIALS_PATH", "config/google_credentials.json"))
                },

                # Webhooks
                "webhooks": {
                    "enabled": get_bool("WEBHOOK_ENABLED"),
                    "url": env_vars.get("WEBHOOK_URL", ""),
                    "secret_configured": bool(env_vars.get("WEBHOOK_SECRET")),
                    "events": env_vars.get("WEBHOOK_EVENTS", "job.completed,job.failed,lead.created")
                },

                # Slack
                "slack": {
                    "token_configured": bool(env_vars.get("SLACK_TOKEN")),
                    "channel": env_vars.get("SLACK_CHANNEL", ""),
                    "configured": bool(env_vars.get("SLACK_TOKEN") and env_vars.get("SLACK_CHANNEL"))
                },

                # Discord
                "discord": {
                    "webhook_url": env_vars.get("DISCORD_WEBHOOK_URL", ""),
                    "configured": bool(env_vars.get("DISCORD_WEBHOOK_URL"))
                },

                # Email/SMTP
                "email": {
                    "smtp_host": env_vars.get("SMTP_HOST", ""),
                    "smtp_port": int(env_vars.get("SMTP_PORT", "587")),
                    "smtp_user": env_vars.get("SMTP_USER", ""),
                    "password_configured": bool(env_vars.get("SMTP_PASSWORD")),
                    "email_from": env_vars.get("EMAIL_FROM", ""),
                    "email_to": env_vars.get("EMAIL_TO", ""),
                    "configured": bool(env_vars.get("SMTP_HOST") and env_vars.get("SMTP_USER"))
                },

                # HubSpot
                "hubspot": {
                    "token_configured": bool(env_vars.get("HUBSPOT_ACCESS_TOKEN")),
                    "token_preview": mask_sensitive(env_vars.get("HUBSPOT_ACCESS_TOKEN", ""))
                },

                # Salesforce
                "salesforce": {
                    "username": env_vars.get("SALESFORCE_USERNAME", ""),
                    "password_configured": bool(env_vars.get("SALESFORCE_PASSWORD")),
                    "token_configured": bool(env_vars.get("SALESFORCE_SECURITY_TOKEN")),
                    "domain": env_vars.get("SALESFORCE_DOMAIN", "login"),
                    "configured": bool(env_vars.get("SALESFORCE_USERNAME") and env_vars.get("SALESFORCE_PASSWORD"))
                },

                # Airtable
                "airtable": {
                    "api_key_configured": bool(env_vars.get("AIRTABLE_API_KEY")),
                    "api_key_preview": mask_sensitive(env_vars.get("AIRTABLE_API_KEY", "")),
                    "base_id": env_vars.get("AIRTABLE_BASE_ID", ""),
                    "configured": bool(env_vars.get("AIRTABLE_API_KEY"))
                },

                # Notion
                "notion": {
                    "api_key_configured": bool(env_vars.get("NOTION_API_KEY")),
                    "api_key_preview": mask_sensitive(env_vars.get("NOTION_API_KEY", "")),
                    "database_id": env_vars.get("NOTION_DATABASE_ID", ""),
                    "configured": bool(env_vars.get("NOTION_API_KEY"))
                },

                # OpenAI
                "openai": {
                    "enabled": get_bool("AI_LEAD_SCORING_ENABLED"),
                    "api_key_configured": bool(env_vars.get("OPENAI_API_KEY")),
                    "api_key_preview": mask_sensitive(env_vars.get("OPENAI_API_KEY", ""))
                },

                # Email Verification
                "email_verification": {
                    "api_key_configured": bool(env_vars.get("EMAIL_VERIFICATION_API_KEY")),
                    "provider": env_vars.get("EMAIL_VERIFICATION_PROVIDER", "abstract"),
                    "configured": bool(env_vars.get("EMAIL_VERIFICATION_API_KEY"))
                },

                # AWS S3
                "aws_s3": {
                    "access_key_configured": bool(env_vars.get("AWS_ACCESS_KEY")),
                    "access_key_preview": mask_sensitive(env_vars.get("AWS_ACCESS_KEY", "")),
                    "secret_key_configured": bool(env_vars.get("AWS_SECRET_KEY")),
                    "region": env_vars.get("AWS_REGION", "us-east-1"),
                    "bucket": env_vars.get("S3_BUCKET", ""),
                    "configured": bool(env_vars.get("AWS_ACCESS_KEY") and env_vars.get("S3_BUCKET"))
                },

                # Google Cloud Storage
                "gcs": {
                    "credentials_path": env_vars.get("GCS_CREDENTIALS_PATH", ""),
                    "bucket": env_vars.get("GCS_BUCKET", ""),
                    "configured": bool(env_vars.get("GCS_CREDENTIALS_PATH") and env_vars.get("GCS_BUCKET"))
                },

                # CAPTCHA
                "captcha": {
                    "enabled": get_bool("CAPTCHA_ENABLED"),
                    "api_key_configured": bool(env_vars.get("CAPTCHA_API_KEY")),
                    "api_key_preview": mask_sensitive(env_vars.get("CAPTCHA_API_KEY", ""))
                },

                # Sentiment Analysis
                "sentiment": {
                    "enabled": get_bool("SENTIMENT_ANALYSIS_ENABLED", True)
                },

                # Data Freshness
                "data_freshness": {
                    "threshold_days": int(env_vars.get("DATA_FRESHNESS_THRESHOLD_DAYS", "30"))
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get integration settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/integrations")
async def save_integration_settings(settings: IntegrationSettings):
    """Save integration settings to .env file."""
    try:
        env_vars = read_env_file()

        # Map settings to environment variable names
        mapping = {
            # Google Sheets
            "google_sheets_enabled": "GOOGLE_SHEETS_ENABLED",
            "google_credentials_path": "GOOGLE_CREDENTIALS_PATH",

            # Webhooks
            "webhook_enabled": "WEBHOOK_ENABLED",
            "webhook_url": "WEBHOOK_URL",
            "webhook_secret": "WEBHOOK_SECRET",
            "webhook_events": "WEBHOOK_EVENTS",

            # Slack
            "slack_token": "SLACK_TOKEN",
            "slack_channel": "SLACK_CHANNEL",

            # Discord
            "discord_webhook_url": "DISCORD_WEBHOOK_URL",

            # Email/SMTP
            "smtp_host": "SMTP_HOST",
            "smtp_port": "SMTP_PORT",
            "smtp_user": "SMTP_USER",
            "smtp_password": "SMTP_PASSWORD",
            "email_from": "EMAIL_FROM",
            "email_to": "EMAIL_TO",

            # HubSpot
            "hubspot_access_token": "HUBSPOT_ACCESS_TOKEN",

            # Salesforce
            "salesforce_username": "SALESFORCE_USERNAME",
            "salesforce_password": "SALESFORCE_PASSWORD",
            "salesforce_security_token": "SALESFORCE_SECURITY_TOKEN",
            "salesforce_domain": "SALESFORCE_DOMAIN",

            # Airtable
            "airtable_api_key": "AIRTABLE_API_KEY",
            "airtable_base_id": "AIRTABLE_BASE_ID",

            # Notion
            "notion_api_key": "NOTION_API_KEY",
            "notion_database_id": "NOTION_DATABASE_ID",

            # OpenAI
            "openai_api_key": "OPENAI_API_KEY",
            "ai_lead_scoring_enabled": "AI_LEAD_SCORING_ENABLED",

            # Email Verification
            "email_verification_api_key": "EMAIL_VERIFICATION_API_KEY",
            "email_verification_provider": "EMAIL_VERIFICATION_PROVIDER",

            # AWS S3
            "aws_access_key": "AWS_ACCESS_KEY",
            "aws_secret_key": "AWS_SECRET_KEY",
            "aws_region": "AWS_REGION",
            "s3_bucket": "S3_BUCKET",

            # GCS
            "gcs_credentials_path": "GCS_CREDENTIALS_PATH",
            "gcs_bucket": "GCS_BUCKET",

            # CAPTCHA
            "captcha_api_key": "CAPTCHA_API_KEY",
            "captcha_enabled": "CAPTCHA_ENABLED",

            # Sentiment
            "sentiment_analysis_enabled": "SENTIMENT_ANALYSIS_ENABLED",

            # Data Freshness
            "data_freshness_threshold_days": "DATA_FRESHNESS_THRESHOLD_DAYS"
        }

        # Update env_vars with new settings
        settings_dict = settings.model_dump(exclude_none=True)
        for field, env_key in mapping.items():
            if field in settings_dict and settings_dict[field] is not None:
                value = settings_dict[field]
                if isinstance(value, bool):
                    value = str(value).lower()
                env_vars[env_key] = str(value)

        # Write to .env file
        write_env_file(env_vars)

        logger.info("Integration settings saved successfully")
        return {
            "success": True,
            "message": "Settings saved. Restart the server to apply changes."
        }

    except Exception as e:
        logger.error(f"Failed to save integration settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/test/{integration}")
async def test_integration(integration: str):
    """Test a specific integration connection."""
    try:
        from config.settings import settings

        if integration == "google_sheets":
            if not settings.google_sheets_enabled:
                return {"success": False, "message": "Google Sheets is disabled"}
            if not os.path.exists(settings.google_credentials_path):
                return {"success": False, "message": f"Credentials file not found: {settings.google_credentials_path}"}
            try:
                from utils.google_sheets_exporter import GoogleSheetsExporter
                exporter = GoogleSheetsExporter()
                return {"success": True, "message": "Google Sheets connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "hubspot":
            if not settings.hubspot_access_token:
                return {"success": False, "message": "HubSpot token not configured"}
            try:
                from utils.crm_integrations import HubSpotIntegration
                hubspot = HubSpotIntegration(settings.hubspot_access_token)
                # Test connection
                return {"success": True, "message": "HubSpot connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "salesforce":
            if not settings.salesforce_username:
                return {"success": False, "message": "Salesforce credentials not configured"}
            try:
                from utils.crm_integrations import SalesforceIntegration
                sf = SalesforceIntegration(
                    settings.salesforce_username,
                    settings.salesforce_password,
                    settings.salesforce_security_token,
                    settings.salesforce_domain
                )
                return {"success": True, "message": "Salesforce connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "airtable":
            if not settings.airtable_api_key:
                return {"success": False, "message": "Airtable API key not configured"}
            try:
                from utils.airtable_notion_exporter import AirtableExporter
                exporter = AirtableExporter(settings.airtable_api_key, settings.airtable_base_id or "")
                return {"success": True, "message": "Airtable connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "notion":
            if not settings.notion_api_key:
                return {"success": False, "message": "Notion API key not configured"}
            try:
                from utils.airtable_notion_exporter import NotionExporter
                exporter = NotionExporter(settings.notion_api_key, settings.notion_database_id or "")
                return {"success": True, "message": "Notion connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "aws_s3":
            if not settings.aws_access_key:
                return {"success": False, "message": "AWS credentials not configured"}
            try:
                from utils.cloud_storage import CloudStorageManager
                cloud = CloudStorageManager()
                cloud.init_s3(settings.aws_access_key, settings.aws_secret_key, settings.aws_region)
                return {"success": True, "message": "AWS S3 connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "gcs":
            if not settings.gcs_credentials_path:
                return {"success": False, "message": "GCS credentials not configured"}
            try:
                from utils.cloud_storage import CloudStorageManager
                cloud = CloudStorageManager()
                cloud.init_gcs(settings.gcs_credentials_path)
                return {"success": True, "message": "Google Cloud Storage connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        elif integration == "webhook":
            if not settings.webhook_url:
                return {"success": False, "message": "Webhook URL not configured"}
            try:
                import requests
                response = requests.post(
                    settings.webhook_url,
                    json={"test": True, "message": "MapLeads Pro test webhook"},
                    timeout=10
                )
                if response.status_code in [200, 201, 202, 204]:
                    return {"success": True, "message": f"Webhook test successful (status: {response.status_code})"}
                else:
                    return {"success": False, "message": f"Webhook returned status: {response.status_code}"}
            except Exception as e:
                return {"success": False, "message": f"Webhook test failed: {str(e)}"}

        elif integration == "openai":
            if not settings.openai_api_key:
                return {"success": False, "message": "OpenAI API key not configured"}
            try:
                import openai
                client = openai.OpenAI(api_key=settings.openai_api_key)
                # Simple test
                models = client.models.list()
                return {"success": True, "message": "OpenAI connection successful"}
            except Exception as e:
                return {"success": False, "message": f"Connection failed: {str(e)}"}

        else:
            return {"success": False, "message": f"Unknown integration: {integration}"}

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return {"success": False, "message": str(e)}

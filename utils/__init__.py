"""Utilities package."""
from .exporter import DataExporter
from .logger import setup_logger

# New feature modules
from .google_sheets_exporter import GoogleSheetsExporter, get_sheets_exporter
from .notifications import NotificationService, get_notification_service
from .crm_integrations import HubSpotIntegration, SalesforceIntegration, CRMManager, get_crm_manager
from .lead_scoring import LeadScorer, get_lead_scorer
from .email_verification import EmailVerifier, get_email_verifier
from .airtable_notion_exporter import AirtableExporter, NotionExporter, ExportManager, get_export_manager

__all__ = [
    # Core
    "DataExporter",
    "setup_logger",
    # Google Sheets
    "GoogleSheetsExporter",
    "get_sheets_exporter",
    # Notifications
    "NotificationService",
    "get_notification_service",
    # CRM
    "HubSpotIntegration",
    "SalesforceIntegration",
    "CRMManager",
    "get_crm_manager",
    # Lead Scoring
    "LeadScorer",
    "get_lead_scorer",
    # Email Verification
    "EmailVerifier",
    "get_email_verifier",
    # Airtable/Notion
    "AirtableExporter",
    "NotionExporter",
    "ExportManager",
    "get_export_manager",
]

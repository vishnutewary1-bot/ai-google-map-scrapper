"""Feature flags module - single source of truth for feature availability."""
from loguru import logger


class FeatureFlags:
    """
    Centralized feature flags for the application.

    Instead of having try-except blocks scattered across 16+ files,
    all feature availability checks are consolidated here.
    """

    # Core features
    HAS_DATABASE = False
    HAS_EXPORTER = False
    HAS_SHEETS = False

    # AI features
    HAS_OPENAI = False
    HAS_SENTIMENT = False

    # Scraper features
    HAS_SCRAPE_FILTERS = False
    HAS_EMAIL_GUESSER = False
    HAS_WHATSAPP_DETECTOR = False
    HAS_HOURS_ANALYZER = False
    HAS_REVIEW_ANALYZER = False
    HAS_WEBSITE_ANALYZER = False

    # Export features
    HAS_OPENPYXL = False
    HAS_CLOUD_STORAGE = False
    HAS_PDF_EXPORT = False

    # Integration features
    HAS_CRM = False
    HAS_AIRTABLE = False
    HAS_NOTION = False

    _initialized = False

    @classmethod
    def initialize(cls):
        """
        Initialize all feature flags once at startup.

        This should be called once when the application starts,
        replacing all the scattered try-except blocks throughout the codebase.
        """
        if cls._initialized:
            return

        # Database
        try:
            from database import db_manager
            cls.HAS_DATABASE = True
            logger.debug("Feature: Database available")
        except ImportError:
            logger.debug("Feature: Database not available")

        # Exporter
        try:
            from utils.exporter import DataExporter
            cls.HAS_EXPORTER = True
            logger.debug("Feature: Exporter available")
        except ImportError:
            logger.debug("Feature: Exporter not available")

        # Google Sheets
        try:
            from utils.google_sheets_exporter import GoogleSheetsExporter
            cls.HAS_SHEETS = True
            logger.debug("Feature: Google Sheets available")
        except ImportError:
            logger.debug("Feature: Google Sheets not available")

        # OpenAI
        try:
            import openai
            cls.HAS_OPENAI = True
            logger.debug("Feature: OpenAI available")
        except ImportError:
            logger.debug("Feature: OpenAI not available")

        # Sentiment Analysis
        try:
            from textblob import TextBlob
            cls.HAS_SENTIMENT = True
            logger.debug("Feature: Sentiment analysis available")
        except ImportError:
            logger.debug("Feature: Sentiment analysis not available")

        # Scrape Filters
        try:
            from utils.scrape_filters import ScrapeFilterProcessor
            cls.HAS_SCRAPE_FILTERS = True
            logger.debug("Feature: Scrape filters available")
        except ImportError:
            logger.debug("Feature: Scrape filters not available")

        # Email Guesser
        try:
            from utils.email_guesser import guess_business_emails
            cls.HAS_EMAIL_GUESSER = True
            logger.debug("Feature: Email guesser available")
        except ImportError:
            logger.debug("Feature: Email guesser not available")

        # WhatsApp Detector
        try:
            from utils.whatsapp_detector import detect_whatsapp
            cls.HAS_WHATSAPP_DETECTOR = True
            logger.debug("Feature: WhatsApp detector available")
        except ImportError:
            logger.debug("Feature: WhatsApp detector not available")

        # Hours Analyzer
        try:
            from utils.hours_analyzer import analyze_business_hours
            cls.HAS_HOURS_ANALYZER = True
            logger.debug("Feature: Hours analyzer available")
        except ImportError:
            logger.debug("Feature: Hours analyzer not available")

        # Review Analyzer
        try:
            from utils.review_analyzer import analyze_reviews
            cls.HAS_REVIEW_ANALYZER = True
            logger.debug("Feature: Review analyzer available")
        except ImportError:
            logger.debug("Feature: Review analyzer not available")

        # Website Analyzer
        try:
            from utils.website_analyzer import WebsiteAnalyzer, analyze_website
            cls.HAS_WEBSITE_ANALYZER = True
            logger.debug("Feature: Website analyzer available")
        except ImportError:
            logger.debug("Feature: Website analyzer not available")

        # OpenPyXL (Excel export)
        try:
            from openpyxl import Workbook
            cls.HAS_OPENPYXL = True
            logger.debug("Feature: Excel export (openpyxl) available")
        except ImportError:
            logger.debug("Feature: Excel export (openpyxl) not available")

        # Cloud Storage
        try:
            from utils.cloud_storage import CloudStorageManager
            cls.HAS_CLOUD_STORAGE = True
            logger.debug("Feature: Cloud storage available")
        except ImportError:
            logger.debug("Feature: Cloud storage not available")

        # PDF Export
        try:
            from utils.pdf_exporter import PDFExporter
            cls.HAS_PDF_EXPORT = True
            logger.debug("Feature: PDF export available")
        except ImportError:
            logger.debug("Feature: PDF export not available")

        # CRM Integrations
        try:
            from utils.crm_integrations import CRMManager
            cls.HAS_CRM = True
            logger.debug("Feature: CRM integrations available")
        except ImportError:
            logger.debug("Feature: CRM integrations not available")

        # Airtable
        try:
            from utils.airtable_notion_exporter import AirtableExporter
            cls.HAS_AIRTABLE = True
            logger.debug("Feature: Airtable available")
        except ImportError:
            logger.debug("Feature: Airtable not available")

        # Notion
        try:
            from utils.airtable_notion_exporter import NotionExporter
            cls.HAS_NOTION = True
            logger.debug("Feature: Notion available")
        except ImportError:
            logger.debug("Feature: Notion not available")

        cls._initialized = True
        logger.info("Feature flags initialized")

    @classmethod
    def get_status(cls) -> dict:
        """Get status of all feature flags."""
        if not cls._initialized:
            cls.initialize()

        return {
            "database": cls.HAS_DATABASE,
            "exporter": cls.HAS_EXPORTER,
            "google_sheets": cls.HAS_SHEETS,
            "openai": cls.HAS_OPENAI,
            "sentiment": cls.HAS_SENTIMENT,
            "scrape_filters": cls.HAS_SCRAPE_FILTERS,
            "email_guesser": cls.HAS_EMAIL_GUESSER,
            "whatsapp_detector": cls.HAS_WHATSAPP_DETECTOR,
            "hours_analyzer": cls.HAS_HOURS_ANALYZER,
            "review_analyzer": cls.HAS_REVIEW_ANALYZER,
            "website_analyzer": cls.HAS_WEBSITE_ANALYZER,
            "excel_export": cls.HAS_OPENPYXL,
            "cloud_storage": cls.HAS_CLOUD_STORAGE,
            "pdf_export": cls.HAS_PDF_EXPORT,
            "crm": cls.HAS_CRM,
            "airtable": cls.HAS_AIRTABLE,
            "notion": cls.HAS_NOTION,
        }

    @classmethod
    def reset(cls):
        """Reset all feature flags (useful for testing)."""
        cls.HAS_DATABASE = False
        cls.HAS_EXPORTER = False
        cls.HAS_SHEETS = False
        cls.HAS_OPENAI = False
        cls.HAS_SENTIMENT = False
        cls.HAS_SCRAPE_FILTERS = False
        cls.HAS_EMAIL_GUESSER = False
        cls.HAS_WHATSAPP_DETECTOR = False
        cls.HAS_HOURS_ANALYZER = False
        cls.HAS_REVIEW_ANALYZER = False
        cls.HAS_WEBSITE_ANALYZER = False
        cls.HAS_OPENPYXL = False
        cls.HAS_CLOUD_STORAGE = False
        cls.HAS_PDF_EXPORT = False
        cls.HAS_CRM = False
        cls.HAS_AIRTABLE = False
        cls.HAS_NOTION = False
        cls._initialized = False


# Auto-initialize on import
FeatureFlags.initialize()

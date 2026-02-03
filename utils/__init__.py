"""Utilities package."""
from .exporter import DataExporter
from .logger import setup_logger

# New feature modules (with optional imports)
try:
    from .google_sheets_exporter import GoogleSheetsExporter, get_sheets_exporter
except ImportError:
    GoogleSheetsExporter = None
    get_sheets_exporter = None

try:
    from .notifications import NotificationService, get_notification_service
except ImportError:
    NotificationService = None
    get_notification_service = None

try:
    from .crm_integrations import HubSpotIntegration, SalesforceIntegration, CRMManager, get_crm_manager
except ImportError:
    HubSpotIntegration = None
    SalesforceIntegration = None
    CRMManager = None
    get_crm_manager = None

try:
    from .lead_scoring import LeadScorer, EnhancedLeadScorer, ScoringWeights, get_lead_scorer, get_enhanced_scorer
except ImportError:
    LeadScorer = None
    EnhancedLeadScorer = None
    ScoringWeights = None
    get_lead_scorer = None
    get_enhanced_scorer = None

try:
    from .email_verification import EmailVerifier, get_email_verifier
except ImportError:
    EmailVerifier = None
    get_email_verifier = None

try:
    from .airtable_notion_exporter import AirtableExporter, NotionExporter, ExportManager, get_export_manager
except ImportError:
    AirtableExporter = None
    NotionExporter = None
    ExportManager = None
    get_export_manager = None

# New feature implementations (Phase 1-7)
try:
    from .email_guesser import EmailGuesser, guess_business_emails
except ImportError:
    EmailGuesser = None
    guess_business_emails = None

try:
    from .whatsapp_detector import WhatsAppDetector, detect_whatsapp
except ImportError:
    WhatsAppDetector = None
    detect_whatsapp = None

try:
    from .hours_analyzer import HoursAnalyzer, analyze_business_hours
except ImportError:
    HoursAnalyzer = None
    analyze_business_hours = None

try:
    from .deduplicator import AdvancedDeduplicator, deduplicate_leads, find_duplicates
except ImportError:
    AdvancedDeduplicator = None
    deduplicate_leads = None
    find_duplicates = None

try:
    from .review_analyzer import ReviewAnalyzer, analyze_reviews
except ImportError:
    ReviewAnalyzer = None
    analyze_reviews = None

try:
    from .website_analyzer import WebsiteAnalyzer, analyze_website, check_ssl
except ImportError:
    WebsiteAnalyzer = None
    analyze_website = None
    check_ssl = None

try:
    from .pdf_exporter import PDFExporter, export_leads_to_pdf, is_pdf_export_available
except ImportError:
    PDFExporter = None
    export_leads_to_pdf = None
    is_pdf_export_available = lambda: False

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
    "EnhancedLeadScorer",
    "ScoringWeights",
    "get_lead_scorer",
    "get_enhanced_scorer",
    # Email Verification
    "EmailVerifier",
    "get_email_verifier",
    # Airtable/Notion
    "AirtableExporter",
    "NotionExporter",
    "ExportManager",
    "get_export_manager",
    # New Features
    "EmailGuesser",
    "guess_business_emails",
    "WhatsAppDetector",
    "detect_whatsapp",
    "HoursAnalyzer",
    "analyze_business_hours",
    "AdvancedDeduplicator",
    "deduplicate_leads",
    "find_duplicates",
    "ReviewAnalyzer",
    "analyze_reviews",
    "WebsiteAnalyzer",
    "analyze_website",
    "check_ssl",
    "PDFExporter",
    "export_leads_to_pdf",
    "is_pdf_export_available",
]

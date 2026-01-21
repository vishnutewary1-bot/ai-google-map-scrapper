"""
Google Maps Scraper Package v2.0.0

Provides a unified, high-performance scraper for extracting business data
from Google Maps with website enrichment capabilities.

Features:
- Anti-detection browser automation
- 50+ data fields extraction
- Social media link extraction (8 platforms)
- Contact information extraction (emails, phones, contact persons)
- Company insights extraction (employees, founded year, revenue estimation)
- Popular times extraction
- Review extraction
- Deduplication and quality scoring
- Excel, CSV, Google Sheets export
- CRM integrations

Usage:
    from scraper import UnifiedGoogleMapsScraper, ScrapeConfig

    config = ScrapeConfig(
        search_query="restaurants",
        location="New York, NY",
        max_results=100,
        extract_emails=True,
        extract_social=True,
    )

    with UnifiedGoogleMapsScraper() as scraper:
        result = scraper.scrape(config)
        print(f"Found {len(result.leads)} leads")

Quick scrape:
    from scraper import run_scrape

    result = run_scrape("plumbers", location="Los Angeles", max_results=50)
"""

# Main scraper
from .unified_scraper import UnifiedGoogleMapsScraper, ScrapeConfig, ScrapeResult, run_scrape

# Browser engine
from .browser_engine import BrowserEngine

# Extractors
from .extractors import (
    MapsExtractor,
    ContactExtractor,
    ContactInfo,
    ContactPerson,
    SocialMediaExtractor,
    CompanyInsightsExtractor,
    CompanyInsights,
    ReviewExtractor,
    PopularTimesExtractor,
    get_maps_extractor,
    get_review_extractor,
    get_popular_times_extractor,
    social_media_extractor,
)

# CAPTCHA solver (optional)
try:
    from .captcha_solver import CaptchaSolver, get_captcha_solver
    HAS_CAPTCHA = True
except ImportError:
    HAS_CAPTCHA = False
    CaptchaSolver = None
    get_captcha_solver = None

# Scheduler (optional)
try:
    from .scheduler import ScrapeScheduler, ScheduledTask, get_scheduler
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    ScrapeScheduler = None
    ScheduledTask = None
    get_scheduler = None

__version__ = "2.0.0"

__all__ = [
    # === Main Scraper ===
    "UnifiedGoogleMapsScraper",
    "ScrapeConfig",
    "ScrapeResult",
    "run_scrape",

    # === Browser Engine ===
    "BrowserEngine",

    # === Extractors ===
    "MapsExtractor",
    "ContactExtractor",
    "ContactInfo",
    "ContactPerson",
    "SocialMediaExtractor",
    "CompanyInsightsExtractor",
    "CompanyInsights",
    "ReviewExtractor",
    "PopularTimesExtractor",

    # === Factory Functions ===
    "get_maps_extractor",
    "get_review_extractor",
    "get_popular_times_extractor",
    "social_media_extractor",

    # === CAPTCHA (if available) ===
    "CaptchaSolver",
    "get_captcha_solver",

    # === Scheduler (if available) ===
    "ScrapeScheduler",
    "ScheduledTask",
    "get_scheduler",
]

"""Scraper package."""
from .google_maps_scraper import GoogleMapsScraper
from .browser_manager import BrowserManager
from .extractor import DataExtractor

# New feature modules
from .captcha_solver import CaptchaSolver, get_captcha_solver
from .review_extractor import ReviewExtractor, get_review_extractor
from .scheduler import ScrapeScheduler, ScheduledTask, get_scheduler
from .popular_times_extractor import PopularTimesExtractor, get_popular_times_extractor

__all__ = [
    # Core
    "GoogleMapsScraper",
    "BrowserManager",
    "DataExtractor",
    # CAPTCHA
    "CaptchaSolver",
    "get_captcha_solver",
    # Reviews
    "ReviewExtractor",
    "get_review_extractor",
    # Scheduler
    "ScrapeScheduler",
    "ScheduledTask",
    "get_scheduler",
    # Popular Times
    "PopularTimesExtractor",
    "get_popular_times_extractor",
]

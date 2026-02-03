"""Unified Google Maps Scraper - Single entry point for all scraping operations."""

import os
import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.browser_engine import BrowserEngine
from scraper.extractors import (
    MapsExtractor,
    ContactExtractor,
    SocialMediaExtractor,
    CompanyInsightsExtractor,
    ReviewExtractor,
    PopularTimesExtractor,
)

# Database imports (optional)
try:
    from database import db_manager
    from database.models import BusinessLead, ScrapeJob
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None

# Export utilities (optional)
try:
    from utils.exporter import export_to_excel, export_to_csv
    HAS_EXPORTER = True
except ImportError:
    HAS_EXPORTER = False

try:
    from utils.google_sheets_exporter import GoogleSheetsExporter
    HAS_SHEETS = True
except ImportError:
    HAS_SHEETS = False

# Email guesser (Feature 1.1)
try:
    from utils.email_guesser import guess_business_emails
    HAS_EMAIL_GUESSER = True
except ImportError:
    HAS_EMAIL_GUESSER = False
    guess_business_emails = None

# WhatsApp detector (Feature 1.2)
try:
    from utils.whatsapp_detector import detect_whatsapp
    HAS_WHATSAPP_DETECTOR = True
except ImportError:
    HAS_WHATSAPP_DETECTOR = False
    detect_whatsapp = None

# Hours analyzer (Feature 1.3)
try:
    from utils.hours_analyzer import analyze_business_hours
    HAS_HOURS_ANALYZER = True
except ImportError:
    HAS_HOURS_ANALYZER = False
    analyze_business_hours = None

# Review analyzer (Feature 1.5)
try:
    from utils.review_analyzer import analyze_reviews
    HAS_REVIEW_ANALYZER = True
except ImportError:
    HAS_REVIEW_ANALYZER = False
    analyze_reviews = None

# Website analyzer (Feature 4.1)
try:
    from utils.website_analyzer import WebsiteAnalyzer, analyze_website
    HAS_WEBSITE_ANALYZER = True
except ImportError:
    HAS_WEBSITE_ANALYZER = False
    WebsiteAnalyzer = None
    analyze_website = None

# Pre-scrape filters
try:
    from utils.scrape_filters import ScrapeFilterProcessor
    HAS_SCRAPE_FILTERS = True
except ImportError:
    HAS_SCRAPE_FILTERS = False
    ScrapeFilterProcessor = None


@dataclass
class ScrapeConfig:
    """Configuration for scraping operations."""

    # Required
    search_query: str

    # Location
    location: Optional[str] = None

    # Data source (google_maps, justdial, yellowpages)
    data_source: str = "google_maps"

    # Limits
    max_results: int = 100
    max_workers: int = 3  # For parallel website enrichment

    # Extraction options
    extract_emails: bool = True
    extract_social: bool = True
    extract_contacts: bool = True
    extract_insights: bool = True
    extract_reviews: bool = False
    extract_popular_times: bool = False
    enrich_from_website: bool = True

    # Browser options
    headless: bool = True
    use_proxies: bool = False
    proxy_list: List[str] = field(default_factory=list)
    slow_mo: int = 50

    # Export options
    export_excel: bool = True
    export_sheets: bool = False
    sheets_spreadsheet_id: Optional[str] = None

    # Deduplication
    deduplicate: bool = True
    dedupe_by_place_id: bool = True
    dedupe_by_url: bool = True
    dedupe_by_name_phone: bool = True

    # Callbacks
    on_progress: Optional[Callable[[int, int, str], None]] = None  # current, total, status
    on_lead_found: Optional[Callable[[Dict], None]] = None
    on_error: Optional[Callable[[str, Exception], None]] = None

    # Delays
    min_delay: float = 2.0
    max_delay: float = 5.0
    long_break_interval: int = 10  # Take longer break every N results
    long_break_duration: float = 10.0

    # Pre-scrape filters (applied before saving)
    filters: Optional[Dict] = None

    # Speed optimization
    fast_mode: bool = False  # Enable for 3-5x faster scraping
    parallel_browsers: int = 1  # Number of browser instances for parallel scraping

    def __post_init__(self):
        """Apply fast_mode settings if enabled."""
        if self.fast_mode:
            # Reduce delays for faster scraping
            if self.min_delay == 2.0:  # Only override if using default
                self.min_delay = 0.5
            if self.max_delay == 5.0:
                self.max_delay = 1.5
            if self.long_break_interval == 10:
                self.long_break_interval = 25
            if self.long_break_duration == 10.0:
                self.long_break_duration = 3.0
            # Disable heavy enrichment by default in fast mode
            if self.enrich_from_website and self.extract_reviews == False:
                self.enrich_from_website = False  # Can be explicitly enabled


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""

    success: bool
    leads: List[Dict] = field(default_factory=list)
    total_found: int = 0
    total_saved: int = 0
    duplicates_skipped: int = 0
    filtered_out: int = 0  # Businesses filtered out by pre-scrape filters
    errors: List[str] = field(default_factory=list)
    excel_path: Optional[str] = None
    sheets_url: Optional[str] = None
    duration_seconds: float = 0.0
    stats: Dict = field(default_factory=dict)
    filter_stats: Dict = field(default_factory=dict)  # Filter statistics


class UnifiedGoogleMapsScraper:
    """
    Unified Google Maps Scraper - Main scraper class.

    Combines browser automation, data extraction, website enrichment,
    and export functionality into a single, cohesive interface.
    """

    # Quality score weights
    QUALITY_WEIGHTS = {
        "business_name": 5,
        "phone": 10,
        "email": 15,
        "website": 8,
        "address": 5,
        "city": 3,
        "state": 3,
        "rating": 5,
        "review_count": 5,
        "category": 3,
        "business_hours": 5,
        "facebook": 5,
        "instagram": 5,
        "linkedin": 8,
        "employee_count": 5,
        "founded_year": 5,
        "contact_person": 10,
    }

    def __init__(self):
        """Initialize the scraper."""
        self.browser: Optional[BrowserEngine] = None
        self.maps_extractor = MapsExtractor()
        self.contact_extractor = ContactExtractor()
        self.social_extractor = SocialMediaExtractor()
        self.insights_extractor = CompanyInsightsExtractor()
        self.review_extractor = ReviewExtractor()
        self.popular_times_extractor = PopularTimesExtractor()

        self._seen_place_ids = set()
        self._seen_urls = set()
        self._seen_name_phone = set()

    def scrape(
        self,
        config: ScrapeConfig,
        job_id: Optional[int] = None
    ) -> ScrapeResult:
        """
        Execute a scraping job.

        Args:
            config: Scraping configuration
            job_id: Optional database job ID for tracking

        Returns:
            ScrapeResult with leads and statistics
        """
        start_time = time.time()
        result = ScrapeResult(success=False)

        try:
            # Update job status
            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "running")

            # Launch browser
            logger.info(f"Starting scrape: {config.search_query}")
            self.browser = BrowserEngine(
                headless=config.headless,
                use_proxies=config.use_proxies,
                proxy_list=config.proxy_list,
                slow_mo=config.slow_mo,
            )
            page = self.browser.launch()

            # Navigate to Google Maps
            if not self.browser.navigate_to_maps():
                raise RuntimeError("Failed to navigate to Google Maps")

            # Perform search
            if not self.browser.search(config.search_query, config.location):
                raise RuntimeError("Search failed")

            # Scroll to load results
            self._report_progress(config, 0, config.max_results, "Loading results...")
            listings_count = self.browser.scroll_results(config.max_results, fast_mode=config.fast_mode)
            logger.info(f"Found {listings_count} listings")

            # Get all listings
            listings = self.browser.get_listings()
            result.total_found = len(listings)

            # Process each listing
            for i, listing in enumerate(listings[:config.max_results]):
                try:
                    self._report_progress(
                        config, i + 1, min(len(listings), config.max_results),
                        f"Processing: {listing.get('name', 'Unknown')}"
                    )

                    # Extract data from listing
                    lead_data = self._scrape_listing(listing, config)

                    if not lead_data:
                        continue

                    # Check for duplicates
                    if config.deduplicate and self._is_duplicate(lead_data, config):
                        result.duplicates_skipped += 1
                        logger.debug(f"Skipping duplicate: {lead_data.get('business_name')}")
                        continue

                    # Apply pre-scrape filters (if configured)
                    if config.filters and HAS_SCRAPE_FILTERS and ScrapeFilterProcessor:
                        if not hasattr(self, '_filter_processor'):
                            self._filter_processor = ScrapeFilterProcessor(config.filters)

                        filter_result = self._filter_processor.should_include(lead_data)
                        if not filter_result.passed:
                            result.filtered_out += 1
                            logger.debug(f"Filtered out: {lead_data.get('business_name')} - {filter_result.reason}")
                            continue

                    # Calculate quality score
                    lead_data["quality_score"] = self._calculate_quality_score(lead_data)
                    lead_data["scraped_at"] = datetime.utcnow()  # Use datetime object, not string

                    # Save to database
                    if HAS_DATABASE and job_id:
                        saved = self._save_lead(lead_data, job_id)
                        if saved:
                            result.total_saved += 1

                    result.leads.append(lead_data)

                    # Callback
                    if config.on_lead_found:
                        config.on_lead_found(lead_data)

                    # Random delay
                    self._random_delay(config)

                    # Long break every N results
                    if (i + 1) % config.long_break_interval == 0:
                        logger.info(f"Taking a break after {i + 1} results...")
                        time.sleep(config.long_break_duration)

                except Exception as e:
                    error_msg = f"Error processing listing {i + 1}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

                    if config.on_error:
                        config.on_error(listing.get("name", "Unknown"), e)

            # Export results
            if result.leads:
                if config.export_excel and HAS_EXPORTER:
                    result.excel_path = self._export_excel(result.leads, job_id, config)

                if config.export_sheets and HAS_SHEETS:
                    result.sheets_url = self._export_sheets(result.leads, job_id, config)

            result.success = True
            result.duration_seconds = time.time() - start_time
            result.stats = {
                "total_found": result.total_found,
                "total_saved": result.total_saved,
                "duplicates_skipped": result.duplicates_skipped,
                "filtered_out": result.filtered_out,
                "errors_count": len(result.errors),
                "duration_seconds": result.duration_seconds,
                "avg_quality_score": sum(l.get("quality_score", 0) for l in result.leads) / len(result.leads) if result.leads else 0,
            }

            # Add filter stats if filters were used
            if hasattr(self, '_filter_processor') and self._filter_processor:
                result.filter_stats = self._filter_processor.get_stats()

            # Update job status
            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "completed", result.stats)

            logger.info(f"Scrape completed: {result.total_saved} leads saved in {result.duration_seconds:.1f}s")

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Scrape failed: {e}")

            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "failed", {"error": str(e)})

        finally:
            self.close()
            result.duration_seconds = time.time() - start_time

        return result

    def _scrape_listing(self, listing: Dict, config: ScrapeConfig) -> Optional[Dict]:
        """
        Extract all data from a single listing.

        Args:
            listing: Listing dictionary from browser
            config: Scraping configuration

        Returns:
            Dictionary with all extracted data or None on failure
        """
        try:
            # Click on listing to open details
            if not self.browser.click_listing(listing):
                return None

            page = self.browser.get_page()
            if not page:
                return None

            # Extract basic Maps data
            lead_data = self.maps_extractor.extract(page, config.search_query)

            if not lead_data.get("business_name"):
                logger.warning("Failed to extract business name, skipping")
                self.browser.go_back_to_results()
                return None

            # Extract reviews if enabled
            if config.extract_reviews:
                try:
                    reviews_data = self.review_extractor.extract_reviews(page)
                    lead_data["reviews"] = reviews_data.get("reviews", [])
                    lead_data["reviews_summary"] = reviews_data.get("summary")
                except Exception as e:
                    logger.debug(f"Review extraction failed: {e}")

            # Extract popular times if enabled
            if config.extract_popular_times:
                try:
                    popular_times = self.popular_times_extractor.extract_popular_times(page)
                    lead_data["popular_times"] = popular_times
                except Exception as e:
                    logger.debug(f"Popular times extraction failed: {e}")

            # Go back to results before website enrichment
            self.browser.go_back_to_results()

            # Check if we got email from Google Maps
            maps_email = lead_data.get("email")
            if maps_email:
                logger.info(f"✓ Email found in Google Maps: {maps_email}")

            # Enrich from website if enabled and website exists
            # This will also try to get email if not found in Google Maps
            if config.enrich_from_website and lead_data.get("website"):
                lead_data = self._enrich_from_website(lead_data, config)

                # Log if we found email from website
                if not maps_email and lead_data.get("email"):
                    logger.info(f"✓ Email found from website: {lead_data.get('email')}")
            elif not maps_email and config.extract_emails and lead_data.get("website"):
                # Even if enrich_from_website is False, try to get email if extract_emails is True
                logger.info(f"No email in Maps, trying website: {lead_data.get('website')}")
                lead_data = self._enrich_from_website(lead_data, config)
                if lead_data.get("email"):
                    logger.info(f"✓ Email found from website: {lead_data.get('email')}")

            # Feature 1.1: Email Pattern Guessing
            # If still no email found but we have website, generate guesses
            if HAS_EMAIL_GUESSER and not lead_data.get("email") and lead_data.get("website"):
                guessed = guess_business_emails(
                    website=lead_data.get("website"),
                    business_name=lead_data.get("business_name"),
                    owner_name=lead_data.get("owner_name"),
                    contact_name=lead_data.get("contact_name_1"),
                    max_guesses=5
                )
                if guessed:
                    lead_data["guessed_emails"] = guessed
                    logger.info(f"✓ Generated {len(guessed)} email guesses for {lead_data.get('business_name')}")

            # Feature 1.2: WhatsApp Detection
            if HAS_WHATSAPP_DETECTOR and lead_data.get("phone"):
                wa_result = detect_whatsapp(lead_data["phone"])
                if wa_result.get("likely_whatsapp"):
                    lead_data["whatsapp_number"] = lead_data["phone"]
                    lead_data["whatsapp_link"] = wa_result.get("whatsapp_link")
                    lead_data["whatsapp_likelihood"] = wa_result.get("confidence")
                    logger.debug(f"WhatsApp detected for {lead_data.get('business_name')}: {wa_result.get('confidence')}")

            # Feature 1.3: Business Hours Analysis
            if HAS_HOURS_ANALYZER:
                hours_data = {
                    "monday": lead_data.get("hours_monday"),
                    "tuesday": lead_data.get("hours_tuesday"),
                    "wednesday": lead_data.get("hours_wednesday"),
                    "thursday": lead_data.get("hours_thursday"),
                    "friday": lead_data.get("hours_friday"),
                    "saturday": lead_data.get("hours_saturday"),
                    "sunday": lead_data.get("hours_sunday"),
                }
                # Only analyze if we have at least some hours data
                if any(hours_data.values()):
                    analysis = analyze_business_hours(hours_data)
                    lead_data["hours_analysis"] = analysis
                    lead_data["best_call_times"] = analysis.get("best_call_times")
                    lead_data["total_hours_per_week"] = analysis.get("total_hours_per_week")
                    lead_data["opening_pattern"] = analysis.get("opening_pattern")

            # Feature 1.5: Review Analysis
            if HAS_REVIEW_ANALYZER and lead_data.get("reviews"):
                try:
                    review_analysis = analyze_reviews(lead_data["reviews"])
                    lead_data["review_keywords"] = review_analysis.get("keywords")
                    lead_data["review_trend"] = review_analysis.get("trends", {}).get("trend")
                    lead_data["review_trend_momentum"] = review_analysis.get("trends", {}).get("momentum")
                    lead_data["owner_response_rate"] = review_analysis.get("response_rate", {}).get("response_rate")
                    lead_data["review_highlights"] = review_analysis.get("highlights")
                except Exception as e:
                    logger.debug(f"Review analysis failed: {e}")

            return lead_data

        except Exception as e:
            logger.error(f"Error scraping listing: {e}")
            try:
                self.browser.go_back_to_results()
            except Exception:
                pass
            return None

    def _enrich_from_website(self, lead_data: Dict, config: ScrapeConfig) -> Dict:
        """
        Enrich lead data by scraping their website.

        Args:
            lead_data: Existing lead data with website URL
            config: Scraping configuration

        Returns:
            Enriched lead data
        """
        website = lead_data.get("website")
        if not website:
            return lead_data

        try:
            # Use ThreadPoolExecutor for parallel extraction
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                futures = {}

                # Extract contacts (emails, phones, contact persons)
                if config.extract_contacts or config.extract_emails:
                    futures["contacts"] = executor.submit(
                        self.contact_extractor.extract_from_website, website
                    )

                # Extract social media links
                if config.extract_social:
                    futures["social"] = executor.submit(
                        self.social_extractor.extract_from_website, website
                    )

                # Extract company insights
                if config.extract_insights:
                    futures["insights"] = executor.submit(
                        self.insights_extractor.extract_from_website, website
                    )

                # Collect results
                for key, future in futures.items():
                    try:
                        result = future.result(timeout=30)

                        if key == "contacts":
                            # ContactExtractor returns ContactInfo object, convert to dict
                            if hasattr(result, 'to_dict'):
                                contact_dict = result.to_dict()
                            else:
                                contact_dict = result if isinstance(result, dict) else {}

                            # Get existing email (from Google Maps) - only override if we don't have one
                            existing_email = lead_data.get("email")
                            website_email = contact_dict.get("email_1")

                            if existing_email:
                                # Keep email from Google Maps, add website emails as secondary
                                lead_data["email"] = existing_email
                                if website_email and website_email != existing_email:
                                    lead_data["email_2"] = website_email
                                    lead_data["email_3"] = contact_dict.get("email_2")
                                else:
                                    lead_data["email_2"] = contact_dict.get("email_2")
                                    lead_data["email_3"] = contact_dict.get("email_3")
                            else:
                                # No email from Maps, use website emails
                                lead_data["email"] = website_email
                                lead_data["email_2"] = contact_dict.get("email_2")
                                lead_data["email_3"] = contact_dict.get("email_3")

                            # Additional phones from website
                            lead_data["phone_2"] = contact_dict.get("phone_2")
                            lead_data["phone_3"] = contact_dict.get("phone_3")

                            # Contact persons
                            lead_data["contact_person_1"] = contact_dict.get("contact_name_1")
                            lead_data["contact_title_1"] = contact_dict.get("contact_title_1")
                            lead_data["contact_email_1"] = contact_dict.get("contact_email_1")
                            lead_data["contact_person_2"] = contact_dict.get("contact_name_2")
                            lead_data["contact_title_2"] = contact_dict.get("contact_title_2")
                            lead_data["contact_email_2"] = contact_dict.get("contact_email_2")
                            lead_data["contact_person_3"] = contact_dict.get("contact_name_3")
                            lead_data["contact_title_3"] = contact_dict.get("contact_title_3")
                            lead_data["contact_email_3"] = contact_dict.get("contact_email_3")

                        elif key == "social":
                            # Merge social media links
                            lead_data["facebook"] = result.get("facebook")
                            lead_data["instagram"] = result.get("instagram")
                            lead_data["linkedin"] = result.get("linkedin")
                            lead_data["twitter"] = result.get("twitter")
                            lead_data["youtube"] = result.get("youtube")
                            lead_data["tiktok"] = result.get("tiktok")
                            lead_data["pinterest"] = result.get("pinterest")
                            lead_data["whatsapp"] = result.get("whatsapp")

                        elif key == "insights":
                            # Merge company insights
                            lead_data["employee_count"] = result.get("employee_count")
                            lead_data["employee_range"] = result.get("employee_range")
                            lead_data["founded_year"] = result.get("founded_year")
                            lead_data["company_type"] = result.get("company_type")
                            lead_data["revenue_estimate"] = result.get("revenue_estimate")
                            lead_data["description"] = result.get("description")

                    except Exception as e:
                        logger.debug(f"Enrichment {key} failed: {e}")

        except Exception as e:
            logger.warning(f"Website enrichment failed for {website}: {e}")

        return lead_data

    def _calculate_quality_score(self, lead_data: Dict) -> int:
        """
        Calculate a quality score for the lead based on data completeness.

        Args:
            lead_data: Lead data dictionary

        Returns:
            Quality score (0-100)
        """
        score = 0
        max_score = sum(self.QUALITY_WEIGHTS.values())

        for field, weight in self.QUALITY_WEIGHTS.items():
            value = lead_data.get(field)

            if value:
                # Special handling for some fields
                if field == "review_count" and isinstance(value, int):
                    if value > 100:
                        score += weight
                    elif value > 10:
                        score += weight * 0.7
                    else:
                        score += weight * 0.3
                elif field == "rating" and isinstance(value, (int, float)):
                    if value >= 4.0:
                        score += weight
                    elif value >= 3.0:
                        score += weight * 0.5
                else:
                    score += weight

        # Normalize to 0-100
        return int((score / max_score) * 100)

    def _is_duplicate(self, lead_data: Dict, config: ScrapeConfig) -> bool:
        """Check if lead is a duplicate."""
        # Check by place_id
        if config.dedupe_by_place_id:
            place_id = lead_data.get("place_id")
            if place_id:
                if place_id in self._seen_place_ids:
                    return True
                self._seen_place_ids.add(place_id)

        # Check by URL
        if config.dedupe_by_url:
            url = lead_data.get("maps_url")
            if url:
                if url in self._seen_urls:
                    return True
                self._seen_urls.add(url)

        # Check by name + phone combination
        if config.dedupe_by_name_phone:
            name = lead_data.get("business_name", "").lower().strip()
            phone = lead_data.get("phone", "").strip()
            if name and phone:
                key = f"{name}:{phone}"
                if key in self._seen_name_phone:
                    return True
                self._seen_name_phone.add(key)

        return False

    def _save_lead(self, lead_data: Dict, job_id: int) -> bool:
        """Save lead to database."""
        if not HAS_DATABASE:
            return False

        try:
            # Map field names from extractor to database model
            field_mapping = {
                "address": "full_address",
                "pincode": "pin_code",
                "facebook": "social_facebook",
                "instagram": "social_instagram",
                "twitter": "social_twitter",
                "linkedin": "social_linkedin",
                "youtube": "social_youtube",
                "tiktok": "social_tiktok",
                "pinterest": "social_pinterest",
                "whatsapp": "social_whatsapp",
                "quality_score": "data_quality_score",
                "employee_count": "employees_min",
                "employee_range": "employees",
                "revenue_estimate": "revenue",
                "contact_person_1": "contact_name_1",
                "contact_person_2": "contact_name_2",
                "contact_person_3": "contact_name_3",
                # Feature 1.1: Email guessing - already matches
                # Feature 1.2: WhatsApp - already matches
                # Feature 1.3: Hours analysis - already matches
                # Feature 1.5: Review analysis - already matches
            }

            # Create mapped data
            mapped_data = {}
            for key, value in lead_data.items():
                if value is None:
                    continue
                # Map field name if mapping exists
                db_field = field_mapping.get(key, key)
                # Only include fields that exist in the model
                if hasattr(BusinessLead, db_field):
                    mapped_data[db_field] = value

            with db_manager.get_session() as session:
                # Check for existing lead by place_id or maps_url
                existing = None
                if mapped_data.get("place_id"):
                    existing = session.query(BusinessLead).filter(
                        BusinessLead.place_id == mapped_data.get("place_id")
                    ).first()

                if not existing and mapped_data.get("maps_url"):
                    existing = session.query(BusinessLead).filter(
                        BusinessLead.maps_url == mapped_data.get("maps_url")
                    ).first()

                if existing:
                    # Update existing lead
                    for key, value in mapped_data.items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    # Data freshness tracking
                    existing.last_verified_at = datetime.utcnow()
                    existing.verification_count = (existing.verification_count or 0) + 1
                else:
                    # Create new lead
                    mapped_data['last_verified_at'] = datetime.utcnow()
                    mapped_data['verification_count'] = 1
                    lead = BusinessLead(**mapped_data)
                    session.add(lead)

                session.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save lead: {e}")
            return False

    def _update_job_status(self, job_id: int, status: str, stats: Dict = None):
        """Update job status in database."""
        if not HAS_DATABASE:
            return

        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
                if job:
                    job.status = status
                    if status == "running":
                        job.started_at = datetime.utcnow()
                    elif status in ("completed", "failed"):
                        job.completed_at = datetime.utcnow()
                        if stats:
                            job.leads_scraped = stats.get("total_saved", 0)
                            job.last_error = stats.get("error")
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    def _export_excel(self, leads: List[Dict], job_id: Optional[int], config: ScrapeConfig) -> Optional[str]:
        """Export leads to Excel file."""
        if not HAS_EXPORTER:
            return None

        try:
            filename = f"leads_{config.search_query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            export_to_excel(leads, filepath)
            logger.info(f"Exported to Excel: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return None

    def _export_sheets(self, leads: List[Dict], job_id: Optional[int], config: ScrapeConfig) -> Optional[str]:
        """Export leads to Google Sheets."""
        if not HAS_SHEETS:
            return None

        try:
            exporter = GoogleSheetsExporter()
            sheet_name = f"Leads - {config.search_query} - {datetime.now().strftime('%Y-%m-%d')}"

            if config.sheets_spreadsheet_id:
                url = exporter.export_to_existing_sheet(leads, config.sheets_spreadsheet_id, sheet_name)
            else:
                url = exporter.export_to_new_sheet(leads, sheet_name)

            logger.info(f"Exported to Google Sheets: {url}")
            return url

        except Exception as e:
            logger.error(f"Google Sheets export failed: {e}")
            return None

    def _report_progress(self, config: ScrapeConfig, current: int, total: int, status: str):
        """Report progress via callback."""
        if config.on_progress:
            config.on_progress(current, total, status)

    def _random_delay(self, config: ScrapeConfig):
        """Add random delay between requests."""
        delay = random.uniform(config.min_delay, config.max_delay)
        time.sleep(delay)

    def close(self):
        """Close browser and cleanup resources."""
        if self.browser:
            self.browser.close()
            self.browser = None

        # Clear deduplication sets
        self._seen_place_ids.clear()
        self._seen_urls.clear()
        self._seen_name_phone.clear()

    def scrape_parallel(
        self,
        config: ScrapeConfig,
        job_id: Optional[int] = None,
        num_browsers: int = 3
    ) -> ScrapeResult:
        """
        Scrape using multiple browser instances in parallel for faster results.

        Args:
            config: Scraping configuration
            job_id: Optional database job ID for tracking
            num_browsers: Number of parallel browser instances (default: 3)

        Returns:
            ScrapeResult with combined leads from all browsers
        """
        from multiprocessing import Process, Queue, Manager
        import queue

        start_time = time.time()
        result = ScrapeResult(success=False)

        # Limit browsers to reasonable number
        num_browsers = min(num_browsers, 5)

        logger.info(f"Starting parallel scrape with {num_browsers} browsers")

        try:
            # Update job status
            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "running")

            # First, get all listings with a single browser
            self.browser = BrowserEngine(
                headless=config.headless,
                use_proxies=config.use_proxies,
                proxy_list=config.proxy_list,
                slow_mo=config.slow_mo,
            )
            self.browser.launch()

            if not self.browser.navigate_to_maps():
                raise RuntimeError("Failed to navigate to Google Maps")

            if not self.browser.search(config.search_query, config.location):
                raise RuntimeError("Search failed")

            # Scroll to load all results (fast mode)
            self._report_progress(config, 0, config.max_results, "Loading results...")
            self.browser.scroll_results(config.max_results, fast_mode=True)

            # Get all listing URLs
            listings = self.browser.get_listings()
            result.total_found = len(listings)
            logger.info(f"Found {len(listings)} listings to process")

            self.browser.close()
            self.browser = None

            if not listings:
                result.success = True
                return result

            # Split listings among browsers
            listings_per_browser = len(listings) // num_browsers
            listing_chunks = []
            for i in range(num_browsers):
                start_idx = i * listings_per_browser
                if i == num_browsers - 1:
                    # Last browser gets remaining listings
                    listing_chunks.append(listings[start_idx:config.max_results])
                else:
                    listing_chunks.append(listings[start_idx:start_idx + listings_per_browser])

            # Use Manager for shared state
            manager = Manager()
            results_queue = manager.Queue()
            errors_list = manager.list()

            def worker_scrape(chunk_listings, worker_id, results_q, errors_l, cfg_dict):
                """Worker function for parallel scraping."""
                try:
                    worker_scraper = UnifiedGoogleMapsScraper()
                    worker_config = ScrapeConfig(**cfg_dict)
                    worker_config.max_results = len(chunk_listings)

                    worker_scraper.browser = BrowserEngine(
                        headless=worker_config.headless,
                        slow_mo=worker_config.slow_mo,
                    )
                    worker_scraper.browser.launch()

                    leads = []
                    for listing in chunk_listings:
                        try:
                            if not worker_scraper.browser.click_listing(listing):
                                continue

                            page = worker_scraper.browser.get_page()
                            if not page:
                                continue

                            lead_data = worker_scraper.maps_extractor.extract(
                                page, worker_config.search_query
                            )

                            if lead_data.get("business_name"):
                                lead_data["quality_score"] = worker_scraper._calculate_quality_score(lead_data)
                                lead_data["scraped_at"] = datetime.utcnow()
                                leads.append(lead_data)

                            worker_scraper.browser.go_back_to_results()
                            time.sleep(random.uniform(worker_config.min_delay, worker_config.max_delay))

                        except Exception as e:
                            errors_l.append(f"Worker {worker_id}: {str(e)}")
                            continue

                    worker_scraper.close()

                    for lead in leads:
                        results_q.put(lead)

                except Exception as e:
                    errors_l.append(f"Worker {worker_id} failed: {str(e)}")

            # Prepare config as dict for multiprocessing
            config_dict = {
                'search_query': config.search_query,
                'location': config.location,
                'headless': config.headless,
                'slow_mo': config.slow_mo,
                'min_delay': config.min_delay,
                'max_delay': config.max_delay,
                'fast_mode': config.fast_mode,
                'enrich_from_website': False,  # Disable for speed in parallel
            }

            # Start worker processes
            processes = []
            for i, chunk in enumerate(listing_chunks):
                if chunk:  # Only start if chunk has listings
                    p = Process(
                        target=worker_scrape,
                        args=(chunk, i, results_queue, errors_list, config_dict)
                    )
                    processes.append(p)
                    p.start()
                    logger.info(f"Started worker {i} with {len(chunk)} listings")

            # Wait for all processes to complete
            for p in processes:
                p.join(timeout=300)  # 5 minute timeout per worker

            # Collect results from queue
            while True:
                try:
                    lead = results_queue.get_nowait()
                    # Check for duplicates
                    if config.deduplicate and self._is_duplicate(lead, config):
                        result.duplicates_skipped += 1
                        continue

                    # Save to database
                    if HAS_DATABASE and job_id:
                        if self._save_lead(lead, job_id):
                            result.total_saved += 1

                    result.leads.append(lead)

                except queue.Empty:
                    break

            # Collect errors
            result.errors = list(errors_list)

            result.success = True
            result.duration_seconds = time.time() - start_time
            result.stats = {
                "total_found": result.total_found,
                "total_saved": result.total_saved,
                "duplicates_skipped": result.duplicates_skipped,
                "errors_count": len(result.errors),
                "duration_seconds": result.duration_seconds,
                "browsers_used": num_browsers,
                "avg_quality_score": sum(l.get("quality_score", 0) for l in result.leads) / len(result.leads) if result.leads else 0,
            }

            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "completed", result.stats)

            logger.info(f"Parallel scrape completed: {len(result.leads)} leads in {result.duration_seconds:.1f}s")

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Parallel scrape failed: {e}")

            if job_id and HAS_DATABASE:
                self._update_job_status(job_id, "failed", {"error": str(e)})

        finally:
            self.close()
            result.duration_seconds = time.time() - start_time

        return result

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def scrape_justdial(
        self,
        query: str,
        city: str,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Scrape business listings from JustDial (India).

        Args:
            query: Business type/category to search
            city: City name in India
            max_results: Maximum results to return

        Returns:
            List of business data dictionaries
        """
        if not HAS_JUSTDIAL:
            raise ImportError("JustDial extractor not available")

        try:
            # Launch browser if not already running
            if not self.browser:
                self.browser = BrowserEngine(headless=True)
                self.browser.launch()

            page = self.browser.get_page()
            return scrape_justdial(page, query, city, max_results)

        except Exception as e:
            logger.error(f"JustDial scrape failed: {e}")
            return []

    def scrape_yellowpages(
        self,
        query: str,
        location: str,
        max_results: int = 50,
        max_pages: int = 3
    ) -> List[Dict]:
        """
        Scrape business listings from Yellow Pages (USA).

        Args:
            query: Business type/category to search
            location: Location (city, state, or zip)
            max_results: Maximum results to return
            max_pages: Maximum pages to scrape

        Returns:
            List of business data dictionaries
        """
        if not HAS_YELLOWPAGES:
            raise ImportError("Yellow Pages extractor not available")

        try:
            # Launch browser if not already running
            if not self.browser:
                self.browser = BrowserEngine(headless=True)
                self.browser.launch()

            page = self.browser.get_page()
            return scrape_yellowpages(page, query, location, max_results, max_pages)

        except Exception as e:
            logger.error(f"Yellow Pages scrape failed: {e}")
            return []

    def scrape_multi_source(
        self,
        config: ScrapeConfig,
        job_id: Optional[int] = None
    ) -> ScrapeResult:
        """
        Scrape from multiple data sources based on config.

        Args:
            config: Scraping configuration with data_source specified
            job_id: Optional database job ID

        Returns:
            ScrapeResult with leads from specified source
        """
        if config.data_source == "justdial":
            if not HAS_JUSTDIAL:
                return ScrapeResult(success=False, errors=["JustDial extractor not available"])

            leads = self.scrape_justdial(
                query=config.search_query,
                city=config.location or "Mumbai",
                max_results=config.max_results
            )
            return ScrapeResult(
                success=True,
                leads=leads,
                total_found=len(leads),
                total_saved=len(leads)
            )

        elif config.data_source == "yellowpages":
            if not HAS_YELLOWPAGES:
                return ScrapeResult(success=False, errors=["Yellow Pages extractor not available"])

            leads = self.scrape_yellowpages(
                query=config.search_query,
                location=config.location or "New York, NY",
                max_results=config.max_results
            )
            return ScrapeResult(
                success=True,
                leads=leads,
                total_found=len(leads),
                total_saved=len(leads)
            )

        else:
            # Default to Google Maps
            return self.scrape(config, job_id)


def run_scrape(
    search_query: str,
    location: Optional[str] = None,
    max_results: int = 100,
    **kwargs
) -> ScrapeResult:
    """
    Convenience function to run a scrape.

    Args:
        search_query: What to search for
        location: Optional location
        max_results: Maximum results to scrape
        **kwargs: Additional ScrapeConfig options

    Returns:
        ScrapeResult with leads and statistics
    """
    config = ScrapeConfig(
        search_query=search_query,
        location=location,
        max_results=max_results,
        **kwargs
    )

    with UnifiedGoogleMapsScraper() as scraper:
        return scraper.scrape(config)


# CLI entry point for subprocess usage
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Google Maps Scraper")
    parser.add_argument("search_query", help="Search query")
    parser.add_argument("--location", "-l", help="Location filter")
    parser.add_argument("--max-results", "-n", type=int, default=100, help="Max results")
    parser.add_argument("--job-id", "-j", type=int, help="Database job ID")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # Run scrape
    config = ScrapeConfig(
        search_query=args.search_query,
        location=args.location,
        max_results=args.max_results,
        headless=args.headless,
    )

    scraper = UnifiedGoogleMapsScraper()

    try:
        result = scraper.scrape(config, job_id=args.job_id)

        # Output results
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump({
                    "success": result.success,
                    "leads": result.leads,
                    "stats": result.stats,
                    "errors": result.errors,
                }, f, indent=2, default=str)
            print(f"Results saved to: {args.output}")
        else:
            print(json.dumps(result.stats, indent=2))

        sys.exit(0 if result.success else 1)

    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        sys.exit(1)

    finally:
        scraper.close()

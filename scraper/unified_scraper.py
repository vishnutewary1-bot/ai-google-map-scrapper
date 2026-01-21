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


@dataclass
class ScrapeConfig:
    """Configuration for scraping operations."""

    # Required
    search_query: str

    # Location
    location: Optional[str] = None

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


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""

    success: bool
    leads: List[Dict] = field(default_factory=list)
    total_found: int = 0
    total_saved: int = 0
    duplicates_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    excel_path: Optional[str] = None
    sheets_url: Optional[str] = None
    duration_seconds: float = 0.0
    stats: Dict = field(default_factory=dict)


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
            listings_count = self.browser.scroll_results(config.max_results)
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
                "errors_count": len(result.errors),
                "duration_seconds": result.duration_seconds,
                "avg_quality_score": sum(l.get("quality_score", 0) for l in result.leads) / len(result.leads) if result.leads else 0,
            }

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

            # Enrich from website if enabled and website exists
            if config.enrich_from_website and lead_data.get("website"):
                lead_data = self._enrich_from_website(lead_data, config)

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
                            # Merge contact info
                            lead_data["email"] = result.get("email") or lead_data.get("email")
                            lead_data["email_2"] = result.get("email_2")
                            lead_data["email_3"] = result.get("email_3")
                            lead_data["phone_2"] = result.get("phone_2")
                            lead_data["phone_3"] = result.get("phone_3")

                            # Contact persons
                            contacts = result.get("contact_persons", [])
                            if contacts:
                                lead_data["contact_person_1"] = contacts[0].get("name") if len(contacts) > 0 else None
                                lead_data["contact_title_1"] = contacts[0].get("title") if len(contacts) > 0 else None
                                lead_data["contact_email_1"] = contacts[0].get("email") if len(contacts) > 0 else None
                                lead_data["contact_person_2"] = contacts[1].get("name") if len(contacts) > 1 else None
                                lead_data["contact_title_2"] = contacts[1].get("title") if len(contacts) > 1 else None
                                lead_data["contact_email_2"] = contacts[1].get("email") if len(contacts) > 1 else None
                                lead_data["contact_person_3"] = contacts[2].get("name") if len(contacts) > 2 else None
                                lead_data["contact_title_3"] = contacts[2].get("title") if len(contacts) > 2 else None
                                lead_data["contact_email_3"] = contacts[2].get("email") if len(contacts) > 2 else None

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
                else:
                    # Create new lead
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

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


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
